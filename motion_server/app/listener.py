"""TCP listener acquisition and expected startup failures."""

from contextlib import contextmanager
import socket
import sys


class ListenerStartupException(Exception):
    def __init__(self, host, port, stage, error):
        self.host = host
        self.port = port
        self.stage = stage
        self.error = error
        super().__init__(str(error))


def log_listener_startup_failure(exception):
    error = exception.error
    print(
        "Motion Server TCP listener startup failed.\n"
        f"- Endpoint: {exception.host}:{exception.port}\n"
        f"- Stage: {exception.stage}\n"
        f"- errno: {error.errno}\n"
        f"- winerror: {getattr(error, 'winerror', None)}\n"
        f"- Detail: {error}",
        flush=True,
    )


@contextmanager
def open_listener(host, port):
    server = None
    stage = "socket"
    try:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            stage = "setsockopt"
            # Windows REUSEADDR permits competing listeners on an occupied port.
            option = (socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32"
                      else socket.SO_REUSEADDR)
            server.setsockopt(socket.SOL_SOCKET, option, 1)
            stage = "bind"
            server.bind((host, port))
            stage = "listen"
            server.listen(1)
        except OSError as error:
            raise ListenerStartupException(host, port, stage, error) from error
        # Loop errors are not listener startup failures.
        yield server
    finally:
        if server is not None:
            failing = sys.exc_info()[0] is not None
            try:
                server.close()
            except OSError as error:
                if not failing:
                    raise
                print(f"TCP listener cleanup failed: {error}", flush=True)
