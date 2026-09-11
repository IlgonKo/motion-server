"""Test-only JSON-line proxy; delays one response without delaying feedback."""
import json
import select
import socket
import threading
import time


class ResponseDelayProxy:
    def __init__(self, server_port):
        self.server_port = server_port
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.port = self.listener.getsockname()[1]
        self.done = threading.Event()
        self.delayed = threading.Event()
        self.delivered = threading.Event()
        self.command = None
        self.delay = 4
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def close(self):
        self.done.set()
        self.thread.join(3)
        self.listener.close()
        if self.thread.is_alive():
            raise AssertionError('Proxy did not terminate')
        if self.error:
            raise self.error

    def run(self):
        downstream = upstream = None
        try:
            while not self.done.is_set():
                try:
                    downstream, _ = self.listener.accept()
                    break
                except socket.timeout:
                    pass
            if downstream is None:
                return
            end = time.monotonic()+10
            while not self.done.is_set():
                try:
                    upstream = socket.create_connection(('127.0.0.1', self.server_port), timeout=.1)
                    break
                except OSError:
                    if time.monotonic() > end:
                        raise
                    time.sleep(.02)
            if upstream is None:
                return
            downstream.settimeout(1)
            upstream.settimeout(1)
            buffers = {downstream: b'', upstream: b''}
            commands = {}
            pending = []
            while not self.done.is_set():
                for source in select.select([downstream, upstream], [], [], .01)[0]:
                    data = source.recv(65536)
                    if not data:
                        return
                    buffers[source] += data
                    while b'\n' in buffers[source]:
                        line, buffers[source] = buffers[source].split(b'\n', 1)
                        message = json.loads(line)
                        request_id = message.get('request_id')
                        if source is downstream:
                            commands[request_id] = message.get('cmd')
                            upstream.sendall(line+b'\n')
                        elif (self.command is not None and request_id is not None
                              and commands.get(request_id) == self.command):
                            self.command = None
                            pending.append((time.monotonic()+self.delay, line+b'\n'))
                            self.delayed.set()
                        else:
                            downstream.sendall(line+b'\n')
                for due, line in pending[:]:
                    if time.monotonic() >= due:
                        downstream.sendall(line)
                        pending.remove((due, line))
                        self.delivered.set()
        except (ConnectionError, OSError) as exc:
            if not self.done.is_set():
                # Normal client shutdown may reset a connection with queued feedback.
                if not isinstance(exc, ConnectionError):
                    self.error = exc
        except Exception as exc:
            self.error = exc
        finally:
            for endpoint in (upstream, downstream):
                if endpoint is not None:
                    endpoint.close()
