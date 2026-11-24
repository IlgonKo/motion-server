from dataclasses import replace
import io
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from configuration import ConfigurationSource
from configuration.builder import build_file_log_config
from configuration.models import FileLogConfig
from motion_server.application import MotionServerApplication
from motion_server.file_logging import AsyncFileLog, FileLoggingSession
from motion_server.runtime_logging import RuntimeLogger


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("file logging condition did not become true")


class FileLoggingTests(unittest.TestCase):
    def test_overflow_does_not_count_successful_inflight_write_as_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            entered, release = threading.Event(), threading.Event()
            original = AsyncFileLog._write
            def slow_write(writer, record):
                if record[2] == "inflight":
                    entered.set()
                    if not release.wait(3):
                        raise OSError("test write wait expired")
                return original(writer, record)
            with patch.object(AsyncFileLog, "_write", slow_write):
                writer = AsyncFileLog(FileLogConfig(True, path), capacity=2)
                try:
                    writer.submit("INFO", "inflight")
                    self.assertTrue(entered.wait(3))
                    for message in ("old queued", "new queued", "last queued"):
                        writer.submit("INFO", message)
                finally:
                    release.set()
                    writer.close()
            text = path.read_text(encoding="utf-8")
            self.assertIn("inflight", text)
            self.assertNotIn("old queued", text)
            self.assertIn("lost_records=1", text)
            self.assertNotIn("lost_records=2", text)

    def test_diagnostic_transitions_are_logged_once_not_each_poll(self):
        from motion_server.diagnostic import DiagnosticManager
        from motion_server.diagnostic.definitions import AXIS_DRIVE_FAULT
        from motion_server.diagnostic.models import DiagnosticSource, DiagnosticSourceType
        from contextlib import redirect_stdout
        manager = DiagnosticManager()
        source = DiagnosticSource(DiagnosticSourceType.AXIS, 0)
        output = io.StringIO()
        with redirect_stdout(output):
            status = manager.detect(AXIS_DRIVE_FAULT, source)
            manager.detect(AXIS_DRIVE_FAULT, source)
            manager.resolve(AXIS_DRIVE_FAULT.code, source)
            manager.resolve(AXIS_DRIVE_FAULT.code, source)
            manager.acknowledge(status.diagnostic_id)
        text = output.getvalue()
        for event in ("detected", "resolved", "acknowledged", "cleared"):
            self.assertEqual(text.count("Diagnostic " + event + ":"), 1)

    def test_configuration_path_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            config = build_file_log_config({"MOTION_SERVER_LOG_FILE_ENABLED": "1",
                "MOTION_SERVER_LOG_FILE_PATH": "logs/server.log"}, Path(directory))
            self.assertEqual(config.path, Path(directory) / "logs/server.log")
            self.assertEqual(config.max_bytes, 10485760)
            self.assertEqual(config.backup_count, 10)
        self.assertFalse(build_file_log_config({}, Path.cwd()).enabled)
        for values in ({"MOTION_SERVER_LOG_FILE_ENABLED": "1"},
                       {"MOTION_SERVER_LOG_FILE_MAX_BYTES": "0"},
                       {"MOTION_SERVER_LOG_FILE_BACKUP_COUNT": "-1"}):
            with self.assertRaises(ValueError):
                build_file_log_config(values, Path.cwd())

    def test_disabled_does_not_replace_streams_or_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "never.log"
            original = sys.stdout
            with FileLoggingSession(FileLogConfig(False, path)) as session:
                self.assertIs(sys.stdout, original)
                self.assertIsNone(session.writer)
            self.assertFalse(path.exists())

    def test_append_unicode_and_rotation_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs/server.log"
            config = FileLogConfig(True, path, 200, 2)
            for batch in range(2):
                writer = AsyncFileLog(config)
                for i in range(10):
                    writer.submit("INFO", f"한글 entry-{batch}-{i} " + "x" * 50)
                writer.close()
                self.assertFalse(writer._thread.is_alive())
            self.assertIn("entry-1-9", path.read_text(encoding="utf-8"))
            self.assertTrue(Path(str(path) + ".1").exists())
            self.assertTrue(Path(str(path) + ".2").exists())
            self.assertFalse(Path(str(path) + ".3").exists())
            writer = AsyncFileLog(replace(config, max_bytes=10000))
            writer.submit("INFO", "after restart")
            writer.close()
            content = path.read_text(encoding="utf-8")
            self.assertIn("entry-1-9", content)
            self.assertIn("after restart", content)

    def test_initial_open_failure_recovers_and_reports_oldest_record_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "blocked"
            blocker.write_text("not a directory", encoding="utf-8")
            path = blocker / "server.log"
            notices = []
            writer = AsyncFileLog(FileLogConfig(True, path), notify=notices.append,
                                  capacity=3, retry_seconds=0.03)
            try:
                wait_until(lambda: notices)
                for i in range(10):
                    writer.submit("INFO", f"record-{i}")
                blocker.unlink()
                wait_until(lambda: path.exists() and "record-9" in path.read_text(encoding="utf-8"))
            finally:
                writer.close()
            text = path.read_text(encoding="utf-8")
            self.assertIn("lost_records=7", text)
            self.assertNotIn("record-0", text)
            self.assertIn("record-7", text)
            self.assertEqual(len(notices), 1)

    def test_write_failure_retries_without_stopping_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            original = AsyncFileLog._write
            fail = [True]
            notices = []
            def injected(writer, record):
                if fail[0]:
                    raise OSError("simulated disk full")
                return original(writer, record)
            with patch.object(AsyncFileLog, "_write", injected):
                writer = AsyncFileLog(FileLogConfig(True, path), notify=notices.append,
                                      retry_seconds=0.02)
                try:
                    writer.submit("INFO", "retained")
                    wait_until(lambda: notices)
                    writer.submit("WARNING", "still running")
                    fail[0] = False
                    wait_until(lambda: path.exists() and "still running" in path.read_text(encoding="utf-8"))
                finally:
                    writer.close()
            self.assertIn("retained", path.read_text(encoding="utf-8"))
            self.assertEqual(len(notices), 1)

    def test_duplicate_file_is_rejected_then_recovered_after_owner_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            config = FileLogConfig(True, path)
            first = AsyncFileLog(config)
            first.submit("INFO", "owner")
            wait_until(lambda: path.exists() and "owner" in path.read_text(encoding="utf-8"))
            notices = []
            second = AsyncFileLog(config, notify=notices.append, retry_seconds=0.02)
            try:
                second.submit("INFO", "second")
                wait_until(lambda: notices)
                self.assertNotIn("second", path.read_text(encoding="utf-8"))
                first.close()
                wait_until(lambda: "second" in path.read_text(encoding="utf-8"))
            finally:
                first.close()
                second.close()

    def test_shutdown_failure_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "directory"
            path.mkdir()
            notices = []
            writer = AsyncFileLog(FileLogConfig(True, path), notify=notices.append)
            writer.submit("INFO", "cannot write")
            wait_until(lambda: notices)
            start = time.monotonic()
            writer.close(timeout=0.1)
            writer._thread.join(0.3)
            self.assertLess(time.monotonic() - start, 0.5)
            self.assertFalse(writer._thread.is_alive())
            self.assertTrue(any("unwritten records" in n for n in notices))

    def test_capture_existing_print_logging_and_traceback_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            console = io.StringIO()
            with patch("sys.stdout", console), patch("sys.stderr", console):
                with FileLoggingSession(FileLogConfig(True, path)):
                    print("startup line")
                    print("traceback detail", file=sys.stderr)
                    logging.getLogger("motion_server.test").warning("api warning")
                    RuntimeLogger._default_logger().info("runtime info")
            text = path.read_text(encoding="utf-8")
            for message in ("startup line", "traceback detail", "api warning", "runtime info"):
                self.assertEqual(text.count(message), 1)
            self.assertIn("WARNING api warning", text)
            self.assertIn("process stopped", text)
            self.assertIn("startup line", console.getvalue())

    def test_configuration_failure_is_also_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "MOTION_SERVER_LOG_FILE_ENABLED=1\nMOTION_SERVER_LOG_FILE_PATH=degraded.log\n"
                "MOTION_SERVER_BUS=invalid_device\n", encoding="utf-8")
            app = MotionServerApplication.from_source(ConfigurationSource(root), environ={})
            self.assertIsNone(app.config)
            def runner(**kwargs):
                print("configuration failure detail")
                return "degraded"
            self.assertEqual(app.run(runner), "degraded")
            self.assertIn("configuration failure detail", (root / "degraded.log").read_text(encoding="utf-8"))

    def test_restart_releases_log_lock_before_new_process(self):
        from motion_server.server import ServerRestartRequested
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "restart.log"
            app = MotionServerApplication(None, file_logging=FileLogConfig(True, path))
            notices = []
            def restart():
                writer = AsyncFileLog(FileLogConfig(True, path), notify=notices.append)
                writer.submit("INFO", "replacement")
                writer.close()
            def runner(**kwargs):
                raise ServerRestartRequested
            with patch("motion_server.server.restart_current_process", side_effect=restart):
                app.run(runner)
            self.assertEqual(notices, [])
            self.assertIn("replacement", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
