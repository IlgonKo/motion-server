from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ethercat.exceptions import EtherCATStateTransitionException
from ethercat.pysoem_master import PySOEMMaster
from motion_server.failure import CommunicationException, map_exception


STATES = SimpleNamespace(INIT_STATE=1, PREOP_STATE=2, SAFEOP_STATE=4, OP_STATE=8)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class PySOEMDCStartupTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.patch = patch("ethercat.pysoem_master.time", self.clock)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.stdout = redirect_stdout(StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.master = PySOEMMaster.__new__(PySOEMMaster)
        self.master._master = Mock(state=2, expected_wkc=3, sdo_read_timeout=700000)
        self.master._master.slaves = []
        self.master._master.receive_processdata.return_value = 0
        self.master._master.state_check.side_effect = lambda target, timeout: target
        self.master._pysoem = STATES
        self.master._load_pysoem = Mock(return_value=STATES)
        self.master.slaves = []
        self.master.cycle_time = 0.002
        self.master.dc_enabled = True
        self.master.dc_sync0_shift_time = 0
        self.master.wkc = 0
        self.master.describe_slaves = Mock(return_value=[{"state": 2, "al_status": 0}])

    def test_dc_traffic_precedes_safeop_and_continues_until_acknowledged(self):
        requests = []
        self.master._master.write_state.side_effect = lambda: requests.append(self.clock.now)
        self.master._master.state_check.side_effect = lambda target, timeout: target if self.clock.now >= 0.240 else 2
        self.master._request_safe_operational(STATES, 1_000_000)
        self.assertGreaterEqual(requests[0], 0.104)
        self.assertLess(requests[0], 0.107)
        self.assertGreater(self.master._master.send_processdata.call_count, 100)
        self.assertTrue(all(call.args[1] == 0 for call in self.master._master.state_check.call_args_list))

    def test_short_deadline_does_not_request_state_before_first_sync0(self):
        with self.assertRaises(EtherCATStateTransitionException) as caught:
            self.master._request_safe_operational(STATES, 50_000)
        self.master._master.write_state.assert_not_called()
        self.assertAlmostEqual(caught.exception.elapsed_s, 0.050)
        self.assertEqual(caught.exception.slaves[0]["al_status"], 0)
        self.assertEqual(map_exception(caught.exception).details, {"operation": "ethercat_state_transition"})

    def test_freerun_needs_no_dc_warmup(self):
        self.master.dc_enabled = False
        self.master._request_safe_operational(STATES, 50_000)
        self.assertEqual(self.clock.now, 0)
        self.master._master.send_processdata.assert_called_once()

    def test_enter_operational_shares_deadline_and_accepts_more_than_50ms(self):
        self.master._configure_sync_parameters = Mock()
        self.master._configure_dc_sync0 = Mock()
        self.master._master.state_check.side_effect = lambda target, timeout: 4 if target == 4 else 4
        with self.assertRaises(EtherCATStateTransitionException) as caught:
            self.master.enter_operational(timeout_s=0.3)
        self.assertEqual(caught.exception.requested_state, "OP")
        self.assertAlmostEqual(self.clock.now, 0.3)
        self.assertLess(caught.exception.elapsed_s, 0.2)

    def test_transport_failure_preserves_typed_error_and_cause(self):
        error = OSError("transport lost")
        self.master._master.send_processdata.side_effect = error
        with self.assertRaises(CommunicationException) as caught:
            self.master._request_safe_operational(STATES, 1_000_000)
        self.assertIs(caught.exception.__cause__, error)

    def test_mapping_cannot_automatically_request_safeop(self):
        master = self.master
        native = master._master
        api = SimpleNamespace(**vars(STATES), Master=Mock(return_value=native))
        master._load_pysoem.return_value = api
        master.interface_name = "test-only"
        master.slave_count = 1
        native.config_init.return_value = 1
        master._register_emergency_callbacks = Mock()
        master._prepare_device_profiles = Mock()
        master._configure_distributed_clocks = Mock()
        native.config_map.side_effect = lambda: self.assertIs(native.manual_state_change, True)
        master.connect(target_state="preop")
        self.assertEqual(native.state, 2)
        self.assertTrue(all(call.args[0] == 2 for call in native.state_check.call_args_list))

    def test_diagnostic_read_failure_is_bounded_and_restores_timeout(self):
        native = self.master._master
        slave = Mock()
        native.slaves = [slave, slave]
        def fail_read(*args):
            self.clock.sleep(native.sdo_read_timeout / 1_000_000)
            raise OSError("unavailable")
        slave.sdo_read.side_effect = fail_read
        values = self.master._read_sync_diagnostics()
        self.assertLessEqual(self.clock.now, 0.100001)
        self.assertTrue(all(item["value"] == "unavailable" for item in values))
        self.assertEqual(native.sdo_read_timeout, 700000)

    def test_diagnostic_readback_keeps_unsigned_mode_and_nanoseconds(self):
        slave = Mock()
        slave.sdo_read.side_effect = lambda index, subindex, size: (2 if subindex == 1 else 2_000_000).to_bytes(size, "little")
        self.master._master.slaves = [slave]
        readings = self.master._read_sync_diagnostics()
        self.assertEqual([item["value"] for item in readings], [2, 2_000_000, 2_000_000] * 2)
        self.assertEqual(self.master._master.sdo_read_timeout, 700000)

    def test_setup_time_counts_against_explicit_recovery_deadline(self):
        self.master._configure_sync_parameters = Mock(side_effect=lambda: self.clock.sleep(0.25))
        self.master._configure_dc_sync0 = Mock()
        with self.assertRaises(EtherCATStateTransitionException):
            self.master.enter_operational(timeout_s=0.3)
        self.assertAlmostEqual(self.clock.now, 0.3)
        self.master._master.write_state.assert_not_called()

    def test_connect_safeop_configures_sync_before_transition(self):
        master = self.master
        native = master._master
        master._load_pysoem.return_value = SimpleNamespace(**vars(STATES), Master=Mock(return_value=native))
        master.interface_name = "test-only"
        master.slave_count = 1
        native.config_init.return_value = 1
        master._register_emergency_callbacks = Mock()
        events = []
        master._prepare_device_profiles = Mock(side_effect=lambda: events.append("pdo"))
        native.config_map.side_effect = lambda: events.append("map")
        master._configure_distributed_clocks = Mock(side_effect=lambda: events.append("dc"))
        master._configure_sync_parameters = Mock(side_effect=lambda: events.append("sync_sdo"))
        master._configure_dc_sync0 = Mock(side_effect=lambda: events.append("sync0"))
        native.write_state.side_effect = lambda: events.append(native.state)
        master.connect(target_state="safeop")
        self.assertEqual(events, [2, "pdo", "map", "dc", "sync_sdo", "sync0", 4])


if __name__ == "__main__":
    unittest.main()
