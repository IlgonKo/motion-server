from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from configuration import ConfigurationSource
from motion_server.application import MotionServerApplication
from motion_server.app.initialization import InitializationStatus
from motion_server.app.session import ServerSession
from motion_server import server
from tests.configuration_fixtures import TEST_NON_PDO_SELECTION


class ServerRestartTest(unittest.TestCase):
    def source(self, directory):
        root = Path(directory)
        self.path = root / '.env'
        self.path.write_text('MOTION_SERVER_BACKEND=mock\nMOTION_SERVER_BUS=axis:cmmt_as\n'
                             + TEST_NON_PDO_SELECTION, encoding='utf-8')
        return ConfigurationSource(root)

    def test_reload_file_and_device_config_creates_fresh_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory)
            device = Path(directory) / 'device/cmmt/.env'
            device.parent.mkdir(parents=True)
            device.write_text('MOTION_SERVER_COMMAND_LOGS=0\n')
            app = MotionServerApplication.from_source(source, environ={})
            seen = []
            def run(**kwargs):
                seen.append(kwargs)
                if len(seen) == 1:
                    with self.path.open('a') as f:
                        f.write('\nMOTION_SERVER_PORT=15432\n')
                    device.write_text('MOTION_SERVER_COMMAND_LOGS=1\n')
                    raise server.ServerRestartRequested
                return 0
            self.assertEqual(app.run(run), 0)
            self.assertEqual(seen[1]['server_config'].port, 15432)
            self.assertIsNot(seen[0]['diagnostic_manager'], seen[1]['diagnostic_manager'])
            self.assertFalse(seen[0]['logging_config'].command.enabled)
            self.assertTrue(seen[1]['logging_config'].command.enabled)

    def test_cli_and_initial_environment_remain_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory)
            env = {'MOTION_SERVER_PORT': '15430', 'PYSOEM_CYCLE_TIME': '0.02'}
            app = MotionServerApplication.from_source(source, argv=['--port', '15431'], environ=env)
            calls = []
            def run(**kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    env['PYSOEM_CYCLE_TIME'] = '0.09'
                    with self.path.open('a') as f: f.write('\nMOTION_SERVER_PORT=15432\n')
                    raise server.ServerRestartRequested
                return 0
            self.assertEqual(app.run(run), 0)
            self.assertEqual(calls[1]['server_config'].port, 15431)
            self.assertEqual(calls[1]['ethercat_config'].cycle.period, .02)

    def test_invalid_bootstrap_reload_exits_without_old_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            app = MotionServerApplication.from_source(self.source(directory), environ={})
            def run(**kwargs):
                with self.path.open('a') as f: f.write('\nMOTION_SERVER_PORT=70000\n')
                raise server.ServerRestartRequested
            self.assertEqual(app.run(run), 1)

    def test_stop_during_reload_prevents_new_session(self):
        with tempfile.TemporaryDirectory() as directory:
            app = MotionServerApplication.from_source(self.source(directory), environ={})
            runner = Mock(side_effect=server.ServerRestartRequested)
            with patch.object(MotionServerApplication, 'from_source', side_effect=KeyboardInterrupt):
                self.assertEqual(app.run(runner), 0)
            self.assertEqual(runner.call_count, 1)

    def test_cleanup_failure_aborts_restart(self):
        app = MotionServerApplication(None)
        with patch.object(MotionServerApplication, 'from_source') as reload:
            self.assertEqual(app.run(Mock(side_effect=server.ServerCleanupError('device close failed'))), 1)
            reload.assert_not_called()

    def test_cleanup_attempts_all_resources_and_closes_clients(self):
        runtime = Mock()
        runtime.close.side_effect = OSError('device close failed')
        session = ServerSession(InitializationStatus.ready(), runtime=runtime)
        clients = [{'id': 1, 'conn': Mock()}, {'id': 2, 'conn': Mock()}]
        sockets = [c['conn'] for c in clients]
        with patch('motion_server.server.close_client', side_effect=RuntimeError('client cleanup')):
            with self.assertRaises(server.ServerCleanupError):
                server.close_server_session(session, clients, {})
        for conn in sockets: conn.close.assert_called_once()
        runtime.close.assert_called_once()
        runtime.parameter_store.close.assert_called_once()
        self.assertIsNone(session.runtime)

    def test_unfinished_file_worker_blocks_new_session(self):
        app = MotionServerApplication(None, reload_inputs=(None, (), {}))
        session = Mock(writer=SimpleNamespace(stopped=False))
        with patch('motion_server.application.FileLoggingSession') as factory:
            factory.return_value.__enter__.return_value = session
            factory.return_value.__exit__.return_value = False
            with patch.object(MotionServerApplication, 'from_source') as reload:
                self.assertEqual(app.run(Mock(side_effect=server.ServerRestartRequested)), 1)
                reload.assert_not_called()
