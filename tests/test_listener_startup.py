from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import errno
import runpy
import socket
import sys
import unittest

from motion_server.app.listener import open_listener, ListenerStartupException
from motion_server.app.initialization import (
    InitializationStage, InitializationStatus, initialization_failure_from_exception,
)
from motion_server.application import MotionServerApplication


class ListenerStartupTest(unittest.TestCase):
    def test_real_listener_rejects_duplicate_and_allows_reopen(self):
        with open_listener("0.0.0.0", 0) as first:
            port = first.getsockname()[1]
            with self.assertRaises(ListenerStartupException) as caught:
                with open_listener("0.0.0.0", port):
                    self.fail("duplicate listener must not start")
            self.assertEqual(caught.exception.stage, "bind")
            with open_listener("0.0.0.0", 0) as independent:
                self.assertNotEqual(independent.getsockname()[1], port)
        with open_listener("0.0.0.0", port) as reopened:
            self.assertEqual(reopened.getsockname()[1], port)

    @unittest.skipUnless(sys.platform == "win32", "Windows socket semantics")
    def test_windows_exclusive_listener_rejects_reuseaddr_competitor(self):
        with open_listener("0.0.0.0", 0) as first:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as competitor:
                competitor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                with self.assertRaises(OSError):
                    competitor.bind(first.getsockname())

    def application(self, configuration_error=False):
        server = SimpleNamespace(port=15000, mode=SimpleNamespace(value="basic"))
        if configuration_error:
            error = ValueError("invalid configuration fixture")
            failure = initialization_failure_from_exception(
                InitializationStage.CONFIGURATION, error,
                occurred_at=datetime.now(timezone.utc))
            return MotionServerApplication(server,
                initialization_status=InitializationStatus.failed(failure),
                initialization_exception=error)
        config = SimpleNamespace(server=server, ethercat=Mock(), motion=Mock(),
                                 logging=Mock(), devices=[])
        return MotionServerApplication(server, config)

    def test_startup_failures_in_all_paths_close_resources_and_return_failure(self):
        for path in ("normal", "degraded", "configuration"):
            for stage in ("socket", "setsockopt", "bind", "listen"):
                for code in (errno.EACCES, errno.EADDRINUSE):
                    with self.subTest(path=path, stage=stage, errno=code):
                        runtime, listener = Mock(), Mock()
                        error = OSError(code, "injected OS error")
                        error.winerror = 10013 if code == errno.EACCES else 10048
                        factory = Mock(return_value=listener)
                        if stage == "socket":
                            factory.side_effect = error
                        else:
                            getattr(listener, stage).side_effect = error
                        def initialize(session, **kwargs):
                            if path == "normal":
                                session.attach_runtime(runtime)
                                return runtime, {}
                            return None, None
                        stdout, stderr = StringIO(), StringIO()
                        with (
                            patch("motion_server.app.listener.socket.socket", factory),
                            patch("motion_server.server.initialize_runtime_session", side_effect=initialize),
                            patch("motion_server.server.build_initialized_server_state", return_value={}),
                            patch("motion_server.server.format_startup_summary", return_value="Startup configuration"),
                            patch("motion_server.server.run_server_loop") as normal_loop,
                            patch("motion_server.server.run_degraded_server_loop") as degraded_loop,
                            redirect_stdout(stdout), redirect_stderr(stderr),
                        ):
                            result = self.application(path == "configuration").run()
                        self.assertEqual(result, 1)
                        self.assertIn("Endpoint: 0.0.0.0:15000", stdout.getvalue())
                        self.assertIn(f"Stage: {stage}", stdout.getvalue())
                        self.assertIn(str(error.winerror), stdout.getvalue())
                        self.assertIn("injected OS error", stdout.getvalue())
                        self.assertNotIn("listening on", stdout.getvalue())
                        self.assertEqual(stderr.getvalue(), "")
                        normal_loop.assert_not_called()
                        degraded_loop.assert_not_called()
                        if stage != "socket":
                            listener.close.assert_called_once()
                        if path == "normal":
                            runtime.close.assert_called_once()

    def test_loop_os_error_is_not_classified_as_startup_failure(self):
        listener = Mock()
        error = OSError(errno.EIO, "loop failure")
        with patch("motion_server.app.listener.socket.socket", return_value=listener):
            with self.assertRaises(OSError) as caught:
                with open_listener("0.0.0.0", 15000):
                    raise error
        self.assertIs(caught.exception, error)
        listener.close.assert_called_once()

    def test_cleanup_os_error_does_not_hide_original_startup_error(self):
        listener = Mock()
        listener.bind.side_effect = OSError(errno.EADDRINUSE, "busy")
        listener.close.side_effect = OSError(errno.EIO, "close failed")
        with patch("motion_server.app.listener.socket.socket", return_value=listener), \
             redirect_stdout(StringIO()) as output:
            with self.assertRaises(ListenerStartupException) as caught:
                with open_listener("0.0.0.0", 15000):
                    self.fail("must not enter")
        self.assertEqual(caught.exception.stage, "bind")
        self.assertIn("close failed", output.getvalue())

    def test_successful_listener_dispatches_each_server_path(self):
        for path in ("normal", "degraded", "configuration"):
            with self.subTest(path=path):
                listener, runtime = Mock(), Mock()
                def initialize(session, **kwargs):
                    if path == "normal":
                        session.attach_runtime(runtime)
                        return runtime, {}
                    return None, None
                with (
                    patch("motion_server.app.listener.socket.socket", return_value=listener),
                    patch("motion_server.server.initialize_runtime_session", side_effect=initialize),
                    patch("motion_server.server.build_initialized_server_state", return_value={}),
                    patch("motion_server.server.format_startup_summary", return_value="Startup configuration"),
                    patch("motion_server.server.run_server_loop", return_value=None) as normal,
                    patch("motion_server.server.run_degraded_server_loop", return_value=None) as degraded,
                    redirect_stdout(StringIO()) as output,
                ):
                    self.assertIsNone(self.application(path == "configuration").run())
                self.assertIn("listening on 0.0.0.0:15000", output.getvalue())
                self.assertEqual(normal.call_count, int(path == "normal"))
                self.assertEqual(degraded.call_count, int(path != "normal"))
                listener.close.assert_called_once()
                if path == "normal":
                    runtime.close.assert_called_once()

    def test_unexpected_setup_error_propagates_and_closes_socket(self):
        listener = Mock()
        listener.bind.side_effect = RuntimeError("programming error")
        with patch("motion_server.app.listener.socket.socket", return_value=listener):
            with self.assertRaisesRegex(RuntimeError, "programming error"):
                with open_listener("0.0.0.0", 15000):
                    self.fail("must not enter")
        listener.close.assert_called_once()

    def test_same_endpoint_succeeds_after_failure_is_removed(self):
        listener = Mock()
        listener.bind.side_effect = [OSError(errno.EADDRINUSE, "busy"), None]
        with patch("motion_server.app.listener.socket.socket", return_value=listener):
            with self.assertRaises(ListenerStartupException):
                with open_listener("0.0.0.0", 15000):
                    self.fail("must not enter")
            with open_listener("0.0.0.0", 15000) as opened:
                self.assertIs(opened, listener)
        self.assertEqual(listener.close.call_count, 2)
        self.assertEqual(listener.bind.call_count, 2)

    def test_python_and_windows_entrypoints_propagate_exit_code(self):
        runtime_module = SimpleNamespace(prepare_runtime=lambda: Path.cwd())
        for packaged in (False, True):
            with self.subTest(packaged=packaged), \
                 patch.object(MotionServerApplication, "from_source") as build, \
                 patch.dict(sys.modules, {"windows_runtime": runtime_module}):
                build.return_value.run.return_value = 1
                with self.assertRaises(SystemExit) as caught:
                    if packaged:
                        runpy.run_path(str(Path(__file__).resolve().parents[1] /
                                           "packaging/windows_motion_server.py"), run_name="__main__")
                    else:
                        runpy.run_module("motion_server.__main__", run_name="__main__")
                self.assertEqual(caught.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
