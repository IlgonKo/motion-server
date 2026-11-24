import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from device.cmmt.profile import CMMTASDeviceProfile
from motion_server.failure import OperationException
from motion_server.handlers.command.jog import start_jog, stop_jog


class JogModeTransitionTest(unittest.TestCase):
    def make_runtime(self, mode="pp", missing=None):
        # Use the real profile mode methods, without loading device configuration.
        profile = object.__new__(CMMTASDeviceProfile)
        rxpdo = SimpleNamespace(
            mode_of_operation=profile.mode_code(mode), controlword=0x000F,
            has_field=lambda name: name != missing,
        )
        samples = []
        runtime = SimpleNamespace(
            slaves=[SimpleNamespace(
                rxpdo=rxpdo, device_profile=profile,
                txpdo=SimpleNamespace(statusword=0x0027),
            )],
            sdo=Mock(), logger=Mock(), cycle_time=0,
            hold_axes=lambda positions, axes: list(positions),
            axis_csp_velocity_offset_enabled=lambda axis: False,
            prepare_processdata=lambda: None,
            send_processdata=lambda: samples.append(
                (rxpdo.mode_of_operation, rxpdo.controlword)
            ),
            receive_processdata=lambda: None,
        )
        state = {
            "motion_modes": [mode], "motion_mode": mode,
            "jog_previous_modes": [None], "target_positions": [0.0],
        }
        return runtime, state, samples

    def test_jog_entry_and_restore_use_only_pdo(self):
        for mode in ("pp", "pv", "csp"):
            with self.subTest(mode=mode):
                runtime, state, samples = self.make_runtime(mode)
                original_code = runtime.slaves[0].rxpdo.mode_of_operation
                start_jog({"cmd": "system/axis/jog_start", "axis": 0,
                           "direction": "positive", "speed": "fast"},
                          runtime, state, None)
                self.assertEqual(samples, [(-3, 0x000F)] * 5)
                self.assertEqual(runtime.slaves[0].rxpdo.controlword, 0x101F)
                self.assertEqual(state["jog_previous_modes"], [mode])
                stop_jog({"cmd": "system/axis/jog_stop", "axis": 0},
                         runtime, state, None)
                self.assertEqual(samples[5:10], [(-3, 0x000F)] * 5)
                self.assertEqual(samples[10:], [(original_code, 0x000F)] * 5)
                self.assertEqual(state["motion_modes"], [mode])
                self.assertEqual(state["jog_previous_modes"], [None])
                self.assertEqual(runtime.sdo.mock_calls, [])

    def test_repeated_jog_updates_direction_without_sdo(self):
        runtime, state, samples = self.make_runtime("jog")
        start_jog({"cmd": "system/axis/jog_start", "axis": 0,
                   "direction": "negative", "speed": "slow"},
                  runtime, state, None)
        self.assertEqual(runtime.slaves[0].rxpdo.mode_of_operation, -3)
        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 0x082F)
        self.assertEqual(samples, [])
        self.assertEqual(runtime.sdo.mock_calls, [])

    def test_missing_mode_mapping_is_rejected_without_sdo_fallback(self):
        runtime, state, samples = self.make_runtime(missing="mode_of_operation")
        with self.assertRaises(OperationException):
            start_jog({"cmd": "system/axis/jog_start", "axis": 0,
                       "direction": "positive"}, runtime, state, None)
        self.assertEqual(samples, [])
        self.assertEqual(state["motion_modes"], ["pp"])
        self.assertEqual(runtime.sdo.mock_calls, [])


if __name__ == "__main__":
    unittest.main()
