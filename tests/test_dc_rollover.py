from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ethercat.distributed_clock import _DcTimeUnwrapper, DcCycleScheduler, DcPhaseLock
from motion_server.failure import CommunicationException
from test_pdo_transport_parity import connected_pysoem


class DcRolloverTest(unittest.TestCase):
    def test_captured_rollover_is_a_normal_two_ms_interval(self):
        clock = _DcTimeUnwrapper(32)
        before = clock.update(4_293_473_308, 0)
        after = clock.update(505_822, 1_999_810)
        self.assertEqual(after - before, 1_999_810)
        self.assertEqual(after, (1 << 32) + 505_822)

    def test_multiple_wraps_keep_phase_and_deadlines_at_one_two_four_ms(self):
        for period in (1_000_000, 2_000_000, 4_000_000):
            with self.subTest(period=period):
                clock = _DcTimeUnwrapper(32)
                phase = DcPhaseLock(True, period / 1e9, 0, 0.1, 0.01, 0.0001)
                scheduler = DcCycleScheduler(phase)
                # Begin on a cycle boundary shortly before the first wrap.
                start = ((1 << 32) // period - 2) * period
                runtime = SimpleNamespace()
                for sample in range(12_000):
                    expected = start + sample * period
                    host = sample * period
                    value = clock.update(expected & 0xFFFFFFFF, host)
                    self.assertEqual(value, expected)
                    self.assertEqual(phase._wrapped_phase_error_ns(value), 0)
                    runtime.last_rx_dc_time_ns = value
                    runtime.last_rx_monotonic_ns = host
                    deadline, wait = scheduler.absolute_cycle_deadline(runtime, host)
                    self.assertAlmostEqual(wait, period / 1e9)
                    self.assertAlmostEqual(deadline, (host + period) / 1e9)
                    runtime.last_tx_monotonic_ns = host + 100_000
                    self.assertEqual(scheduler.estimate_transmit_dc_time_ns(runtime),
                                     expected + 100_000)

    def test_64_bit_clock_preserves_upper_bits_and_small_initial_values(self):
        for initial in (100, (1 << 40) + 123):
            clock = _DcTimeUnwrapper(64)
            self.assertEqual(clock.update(initial, 0), initial)
            self.assertEqual(clock.update(initial + 2_000_000, 2_000_000),
                             initial + 2_000_000)

    def test_reset_or_ambiguous_gap_does_not_mutate_last_good_sample(self):
        for bits, initial, raw, host in (
            (32, 3_000_000_000, 100, 2_000_000),
            (32, 100, 2_000_100, 1 << 31),
            (64, 1 << 40, 100, 2_000_000),
        ):
            clock = _DcTimeUnwrapper(bits)
            clock.update(initial, 0)
            with self.assertRaises(ValueError):
                clock.update(raw, host)
            self.assertEqual(clock.time_ns, initial)
            self.assertEqual(clock.monotonic_ns, 0)

    def test_phase_correction_is_reset_for_new_connection(self):
        phase = DcPhaseLock(True, .002, 0, .1, .01, .0001)
        phase.update(500_000, Mock())
        self.assertNotEqual(phase.correction(), 0)
        phase.reset()
        self.assertEqual(phase.correction(), 0)
        self.assertEqual(phase.integral_error_s, 0)


class PysoemDcRolloverTest(unittest.TestCase):
    def setUp(self):
        self.master, self.native = connected_pysoem((b"\x07",))
        self.master.dc_enabled = True
        self.native.config_dc = Mock(return_value=True)
        self.native.slaves[0]._fprd = Mock(return_value=b"\x07\x04")

    def configure(self):
        with redirect_stdout(StringIO()):
            self.master._configure_distributed_clocks()

    def receive(self, raw, host):
        self.native.dc_time = raw
        self.master.prepare_processdata()
        self.master.send_processdata()
        with patch("ethercat.pysoem_master.time.monotonic_ns", return_value=host):
            self.master.receive_processdata()

    def test_receive_normalizes_once_getters_and_send_use_cached_time(self):
        self.configure()
        self.receive(4_293_473_308, 0)
        self.receive(505_822, 1_999_810)
        expected = (1 << 32) + 505_822
        self.assertEqual(self.master.last_rx_dc_time_ns, expected)
        self.native.dc_time = 123  # Reads must not consume a new sample.
        for _ in range(10):
            self.assertEqual(self.master.get_dc_time_ns(), expected)
        self.master.prepare_processdata()
        self.master.send_processdata()
        self.assertEqual(self.master.last_direct_tx_dc_time_ns, expected)
        self.assertEqual(self.master.last_tx_dc_time_ns, expected)

    def test_first_dc_capable_slave_selects_width_even_with_mixed_slaves(self):
        for features, expected in ((0x0407, 32), (0x018C, 64)):
            non_dc = Mock()
            non_dc._fprd.return_value = b"\x00\x00"
            reference = Mock()
            reference._fprd.return_value = features.to_bytes(2, "little")
            later = Mock()
            self.native.slaves = [non_dc, reference, later]
            self.configure()
            self.assertEqual(self.master._dc_clock.bits, expected)
            reference._fprd.assert_called_once_with(0x0008, 2)
            later._fprd.assert_not_called()

    def test_64_bit_reference_receive_keeps_full_clock(self):
        self.native.slaves[0]._fprd.return_value = b"\x8c\x01"
        self.configure()
        self.receive((1 << 40) + 100, 0)
        self.receive((1 << 40) + 2_000_100, 2_000_000)
        self.assertEqual(self.master.get_dc_time_ns(), (1 << 40) + 2_000_100)

    def test_startup_exchange_seeds_the_same_clock_as_cyclic_receive(self):
        self.configure()
        self.native.state = 2
        self.native.write_state = Mock()
        self.native.state_check = Mock(return_value=4)
        self.native.dc_time = 4_293_473_308
        with patch("ethercat.pysoem_master.time.monotonic_ns", return_value=0):
            with redirect_stdout(StringIO()):
                self.master._transition_with_processdata(4, "SAFE_OP", 1_000_000)
        self.receive(505_822, 1_999_810)
        self.assertEqual(self.master.get_dc_time_ns(), (1 << 32) + 505_822)

    def test_missing_or_unreadable_reference_fails_configuration(self):
        self.native.config_dc.return_value = False
        with self.assertRaises(CommunicationException):
            self.configure()
        self.native.config_dc.return_value = True
        self.native.slaves[0]._fprd.return_value = b""
        with self.assertRaises(CommunicationException):
            self.configure()
        self.native.slaves[0]._fprd.side_effect = OSError("read failed")
        with self.assertRaises(CommunicationException):
            self.configure()

    def test_bad_sample_uses_existing_communication_failure_path(self):
        self.configure()
        self.receive(3_000_000_000, 0)
        with self.assertRaises(CommunicationException):
            self.receive(100, 2_000_000)
        self.assertEqual(self.master.last_rx_dc_time_ns, 3_000_000_000)
        self.assertEqual(self.master.last_rx_monotonic_ns, 0)

    def test_timeout_keeps_previous_sample_and_receive_timestamp(self):
        self.configure()
        self.receive(3_000_000_000, 0)
        self.native.receive_processdata = Mock(return_value=0)
        self.receive(100, 2_000_000)
        self.assertEqual(self.master.last_rx_dc_time_ns, 3_000_000_000)
        self.assertEqual(self.master.last_rx_monotonic_ns, 0)

    def test_reconfiguration_and_reconnect_reset_epoch(self):
        self.configure()
        self.receive(4_293_473_308, 0)
        self.receive(505_822, 1_999_810)
        self.configure()
        self.receive(100, 10_000_000)
        self.assertEqual(self.master.get_dc_time_ns(), 100)
        self.master._reset_processdata_state()
        self.assertIsNone(self.master._dc_clock)
        self.assertIsNone(self.master.last_rx_monotonic_ns)
        self.assertEqual(self.master.get_dc_time_ns(), 0)
        self.configure()
        self.receive(200, 20_000_000)
        self.assertEqual(self.master.get_dc_time_ns(), 200)


if __name__ == "__main__":
    unittest.main()
