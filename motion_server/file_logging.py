"""Process-scoped, bounded asynchronous file output for existing server logs.

The producer only appends to memory. Files, rotation, lock acquisition and retry
belong to the daemon writer. A sidecar OS lock protects the file across rotation.
"""
from collections import deque
from datetime import datetime
import logging
import os
from pathlib import Path
import sys
import threading
import time


class AsyncFileLog:
    def __init__(self, config, *, notify=None, capacity=10000,
                 retry_seconds=5.0, notice_seconds=60.0):
        self.config = config
        self.notify = notify or (lambda message: None)
        self.capacity = capacity
        self.retry_seconds = retry_seconds
        self.notice_seconds = notice_seconds
        self._queue = deque()
        self._condition = threading.Condition()
        self._stopping = False
        self._deadline = None
        self._lost = 0
        self._stream = None
        self._lock_file = None
        self._size = 0
        self._thread = threading.Thread(target=self._run, name="motion-file-log", daemon=True)
        self._thread.start()

    def submit(self, level, message):
        # Bound each record as well as the number of records.
        record = (datetime.now().astimezone().isoformat(timespec="milliseconds"),
                  level, str(message)[:65536])
        with self._condition:
            if self._stopping:
                return
            if len(self._queue) >= self.capacity:
                self._queue.popleft()
                self._lost += 1
            self._queue.append(record)
            self._condition.notify()

    def close(self, timeout=3.0):
        with self._condition:
            if not self._stopping:
                self._stopping = True
                self._deadline = time.monotonic() + timeout
            self._condition.notify_all()
        self._thread.join(max(0.0, timeout))

    def _notice(self, message):
        try:
            self.notify(message)
        except Exception:
            # A diagnostic sink failing must not kill the file writer.
            pass

    def _open(self):
        path = Path(self.config.path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._lock_file is None:
            lock = open(str(path) + ".lock", "a+b")
            try:
                lock.seek(0, 2)
                if lock.tell() == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock.close()
                raise
            self._lock_file = lock
        self._stream = open(path, "ab")
        self._size = self._stream.tell()

    def _write(self, record):
        timestamp, level, text = record
        payload = (f"{timestamp} {level} {text}\n").encode("utf-8", errors="replace")
        if self._size and self._size + len(payload) > self.config.max_bytes:
            self._stream.close()
            self._stream = None
            path = Path(self.config.path).resolve()
            for index in range(self.config.backup_count, 0, -1):
                source = path if index == 1 else Path(f"{path}.{index - 1}")
                if source.exists():
                    os.replace(source, f"{path}.{index}")
            self._stream = open(path, "ab")
            self._size = 0
        self._stream.write(payload)
        self._stream.flush()
        self._size += len(payload)

    def _run(self):
        retry_at = 0.0
        notice_at = float("-inf")
        failed = False
        try:
            while True:
                stop = False
                with self._condition:
                    now = time.monotonic()
                    if self._stopping and (not self._queue or now >= self._deadline):
                        remaining = len(self._queue)
                        stop = True
                    elif now < retry_at:
                        delay = retry_at - now
                        if self._stopping:
                            delay = min(delay, max(0, self._deadline - now))
                        self._condition.wait(delay)
                        continue
                    # Once dequeued, an in-flight write is not a queue overflow
                    # victim. Count only records actually discarded from memory.
                    record = self._queue.popleft() if self._queue and not stop else None
                    if not stop and record is None and self._stream is not None:
                        self._condition.wait()
                        continue
                if stop:
                    if remaining:
                        self._notice(f"File log shutdown deadline: {remaining} unwritten records")
                    return
                try:
                    if self._stream is None:
                        self._open()
                    with self._condition:
                        lost = self._lost
                    if failed or lost:
                        message = f"File logging {'restored' if failed else 'queue overflow'}; lost_records={lost}"
                        self._write((datetime.now().astimezone().isoformat(timespec="milliseconds"),
                                     "WARNING", message))
                        with self._condition:
                            self._lost -= lost
                        failed = False
                    if record is not None:
                        self._write(record)
                except OSError as exc:
                    if record is not None:
                        with self._condition:
                            if len(self._queue) >= self.capacity:
                                # The failed in-flight record is older than the
                                # records queued while I/O was in progress.
                                self._lost += 1
                            else:
                                self._queue.appendleft(record)
                    if self._stream is not None:
                        try:
                            self._stream.close()
                        except OSError:
                            pass
                        self._stream = None
                    now = time.monotonic()
                    if now - notice_at >= self.notice_seconds:
                        self._notice(f"File log unavailable: {self.config.path}: {exc}; retrying")
                        notice_at = now
                    failed = True
                    retry_at = now + self.retry_seconds
        finally:
            if self._stream is not None:
                try:
                    self._stream.close()
                except OSError:
                    pass
            if self._lock_file is not None:
                self._lock_file.close()


class _FileHandler(logging.Handler):
    def __init__(self, writer):
        super().__init__()
        self.writer = writer

    def emit(self, record):
        self.writer.submit(record.levelname, self.format(record))


class _OutputStream:
    """Preserve console output while collecting print/traceback lines per thread."""
    def __init__(self, original, writer, level):
        self.original, self.writer, self.level = original, writer, level
        self.local = threading.local()

    def write(self, text):
        result = self.original.write(text) if self.original is not None else len(text)
        pending = getattr(self.local, "pending", "") + text
        lines = pending.split("\n")
        for line in lines[:-1]:
            self.writer.submit(self.level, line.rstrip("\r"))
        pending = lines[-1]
        if len(pending) >= 65536:
            self.writer.submit(self.level, pending[:65536])
            pending = ""
        self.local.pending = pending
        return result

    def flush(self):
        pending = getattr(self.local, "pending", "")
        if pending:
            self.writer.submit(self.level, pending)
            self.local.pending = ""
        if self.original is not None:
            self.original.flush()

    def __getattr__(self, name):
        return getattr(self.original, name)


class FileLoggingSession:
    """Application lifetime, including degraded startup and final cleanup.

    Existing print sites are captured without changing device/runtime contracts.
    Logging handlers keep the original console stream to avoid double recording.
    """
    def __init__(self, config):
        self.config = config
        self.writer = None

    def __enter__(self):
        if not self.config.enabled:
            return self
        self.stdout, self.stderr = sys.stdout, sys.stderr
        def notify(message):
            if self.stderr is not None:
                self.stderr.write(message + "\n")
                self.stderr.flush()
        self.writer = AsyncFileLog(self.config, notify=notify)
        self.handler = _FileHandler(self.writer)
        self.root = logging.getLogger()
        self.console = None
        if not self.root.handlers:
            self.console = logging.StreamHandler(self.stderr)
            self.root.addHandler(self.console)
        self.root.addHandler(self.handler)
        # RuntimeLogger uses a non-propagating logger and its own console sink.
        from motion_server.runtime_logging import RuntimeLogger
        before = list(logging.getLogger("motion_server.runtime").handlers)
        self.runtime = RuntimeLogger._default_logger()
        self.created_runtime_handlers = [h for h in self.runtime.handlers if h not in before]
        self.runtime.addHandler(self.handler)
        sys.stdout = _OutputStream(self.stdout, self.writer, "INFO")
        sys.stderr = _OutputStream(self.stderr, self.writer, "ERROR")
        self.writer.submit("INFO", "Motion Server process started")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.writer is None:
            return
        try:
            if exc is not None and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
                self.writer.submit("ERROR", f"Motion Server process failed: {exc_type.__name__}: {exc}")
            sys.stdout.flush()
            sys.stderr.flush()
            self.writer.submit("INFO", "Motion Server process stopped")
        finally:
            sys.stdout, sys.stderr = self.stdout, self.stderr
            self.root.removeHandler(self.handler)
            self.runtime.removeHandler(self.handler)
            for handler in self.created_runtime_handlers:
                self.runtime.removeHandler(handler)
                handler.close()
            if self.console is not None:
                self.root.removeHandler(self.console)
            self.writer.close()
