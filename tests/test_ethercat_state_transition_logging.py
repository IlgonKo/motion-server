from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ethercat.exceptions import EtherCATDiscoveryException, EtherCATStateTransitionException
from ethercat.pysoem_master import PySOEMMaster
from motion_server.app.initialization import (
    InitializationCause,
    InitializationStage,
    InitializationStatus,
    initialization_failure_from_exception,
    log_initialization_failure,
)
from motion_server.app.session import ServerSession
from motion_server.server import fail_runtime_initialization
from motion_server.failure import (
    CommunicationException, CommunicationTimeoutException, ConfigurationException,
    DeviceRejectedException, FailureCode, MotionServerException, map_exception,
)
from motion_server.diagnostic import SERVER_INITIALIZATION_FAILED
from motion_server.diagnostic.definitions import SERVER_SOURCE


class EtherCATStateTransitionLoggingTest(unittest.TestCase):
    def master(self):
        master = PySOEMMaster.__new__(PySOEMMaster)
        master._master = Mock()
        master._master.state_check.return_value = 6
        master._master.receive_processdata.return_value = 0
        master.slaves = []
        master.cycle_time = 0.002
        master.dc_enabled = False
        master.dc_sync0_shift_time = 0
        master.describe_slaves = Mock(return_value=[
            {"index": 0, "state": 2, "state_description": "PRE_OP", "al_status": 0},
            {"index": 1, "state": 4, "state_description": "SAFE_OP", "al_status": 0},
        ])
        return master

    def test_state_transition_failures_log_details_without_python_traceback(self):
        pysoem = SimpleNamespace(PREOP_STATE=2, SAFEOP_STATE=4, OP_STATE=8, NONE_STATE=0)
        for method in (
            "_request_pre_operational",
            "_request_safe_operational",
            "_request_operational",
        ):
            with self.subTest(method=method):
                master = self.master()
                try:
                    getattr(master, method)(pysoem, 50000)
                except EtherCATStateTransitionException as exception:
                    failure = initialization_failure_from_exception(
                        InitializationStage.DEVICE_INITIALIZATION,
                        exception,
                        occurred_at=datetime.now(timezone.utc),
                    )
                    stdout, stderr = StringIO(), StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        log_initialization_failure(failure, exception)
                else:
                    self.fail("Expected a typed state transition failure")
                self.assertIs(failure.cause, InitializationCause.DEVICE_INITIALIZATION_FAILED)
                self.assertIn("did not reach", stdout.getvalue())
                self.assertIn("PRE_OP", stdout.getvalue())
                self.assertIn("al_status", stdout.getvalue())
                self.assertNotIn("Traceback", stdout.getvalue())
                self.assertNotIn("Exception", stdout.getvalue())
                self.assertEqual(stderr.getvalue(), "")

    def test_safeop_failure_retains_degraded_status_and_resource_cleanup(self):
        session = ServerSession(InitializationStatus.ready())
        runtime = Mock()
        session.attach_runtime(runtime)
        error = EtherCATStateTransitionException("SAFE_OP", 6)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr:
            failure = fail_runtime_initialization(
                session, runtime, InitializationStage.DEVICE_INITIALIZATION, error
            )
        self.assertFalse(session.initialization_status.initialized)
        self.assertIs(session.initialization_status.failure, failure)
        self.assertIsNone(session.runtime)
        runtime.close.assert_called_once_with()
        self.assertEqual(stderr.getvalue(), "")
        fault = session.diagnostic_manager.status_for(
            SERVER_INITIALIZATION_FAILED.code, SERVER_SOURCE,
        )
        self.assertIsNotNone(fault)
        self.assertEqual(fault.history.occurred_at, failure.occurred_at)

    def test_state_timeout_uses_existing_mapping_without_exposing_internal_details(self):
        error = EtherCATStateTransitionException(
            "SAFE_OP", 6, slaves=[{"name": "private slave detail"}],
        )
        self.assertIsInstance(error, CommunicationTimeoutException)
        mapped = map_exception(error)
        self.assertIs(mapped.code, FailureCode.TIMEOUT)
        self.assertEqual(mapped.details, {"operation": "ethercat_state_transition"})
        self.assertNotIn("private slave detail", str(mapped))

    def test_discovery_failures_are_typed_and_close_transport(self):
        for result, expected_type in (
            (-1, EtherCATDiscoveryException), (0, ConfigurationException),
            (1, ConfigurationException),
        ):
            with self.subTest(result=result):
                master = self.master()
                transport = master._master
                transport.config_init.return_value = result
                master.interface_name = "test-adapter"
                master.slave_count = 2
                master._reset_processdata_state = Mock()
                master.close = Mock()
                master._load_pysoem = Mock(return_value=SimpleNamespace(
                    Master=Mock(return_value=transport),
                ))
                with self.assertRaises(expected_type) as caught:
                    master.connect()
                master.close.assert_called_once_with()
                error = caught.exception
                self.assertIsInstance(error, MotionServerException)
                if result < 0:
                    self.assertIn("result=-1", str(error))
                    self.assertNotIn("found -1", str(error))
                else:
                    self.assertIn(f"found {result}", str(error))
                failure = initialization_failure_from_exception(
                    InitializationStage.BUS_CONNECTION, error,
                    occurred_at=datetime.now(timezone.utc),
                )
                self.assertIs(failure.cause, InitializationCause.BUS_CONNECTION_FAILED)
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr:
                    log_initialization_failure(failure, error)
                self.assertEqual(stderr.getvalue(), "")

    def test_expected_sdo_failures_log_safe_fields_without_traceback(self):
        for error in (
            CommunicationException("sdo_read"),
            CommunicationTimeoutException("sdo_read", 0.05),
            DeviceRejectedException("sdo_write", device_code=0x06010002),
        ):
            with self.subTest(error=type(error).__name__):
                error.__cause__ = OSError("private native detail")
                failure = initialization_failure_from_exception(
                    InitializationStage.DEVICE_INITIALIZATION, error,
                    occurred_at=datetime.now(timezone.utc),
                )
                stdout, stderr = StringIO(), StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    log_initialization_failure(failure, error)
                self.assertIn(error.operation, stdout.getvalue())
                self.assertEqual(stderr.getvalue(), "")
                self.assertIsInstance(error.__cause__, OSError)

    def test_successful_discovery_and_requested_state_failure(self):
        for reached in (2, 6):
            with self.subTest(reached=reached):
                master = self.master()
                transport = master._master
                transport.config_init.return_value = 2
                transport.state_check.return_value = reached
                master.interface_name = "test-adapter"
                master.slave_count = 2
                master._reset_processdata_state = Mock()
                master._register_emergency_callbacks = Mock()
                master._request_pre_operational = Mock()
                master._prepare_device_profiles = Mock()
                master._configure_distributed_clocks = Mock()
                master.close = Mock()
                master._load_pysoem = Mock(return_value=SimpleNamespace(
                    Master=Mock(return_value=transport), PREOP_STATE=2,
                    SAFEOP_STATE=4, OP_STATE=8, INIT_STATE=1,
                ))
                if reached == 2:
                    master.connect(target_state="preop")
                    transport.config_map.assert_called_once_with()
                    master.close.assert_not_called()
                else:
                    with self.assertRaises(EtherCATStateTransitionException) as caught:
                        master.connect(target_state="preop")
                    self.assertEqual(caught.exception.requested_state, "PRE_OP")
                    self.assertEqual(caught.exception.reached_state, 6)
                    master.close.assert_called_once_with()

    def test_missing_pysoem_is_configuration_failure_with_original_cause(self):
        master = self.master()
        master._pysoem = None
        master._add_windows_npcap_dll_paths = Mock()
        with patch.dict("sys.modules", {"pysoem": None}):
            with self.assertRaises(ConfigurationException) as caught:
                master._load_pysoem()
        self.assertIsInstance(caught.exception.__cause__, ImportError)
        self.assertEqual(caught.exception.setting, "MOTION_SERVER_BACKEND")

    def test_unexpected_runtime_error_still_has_diagnostic_traceback(self):
        error = RuntimeError("unexpected internal failure")
        failure = initialization_failure_from_exception(
            InitializationStage.DEVICE_INITIALIZATION,
            error,
            occurred_at=datetime.now(timezone.utc),
        )
        with redirect_stdout(StringIO()), patch("traceback.print_exception") as trace:
            log_initialization_failure(failure, error)
        trace.assert_called_once_with(error)


if __name__ == "__main__":
    unittest.main()
