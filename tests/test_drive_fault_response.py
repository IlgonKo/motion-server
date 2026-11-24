import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from device.cmmt.profile import CMMTASDeviceProfile
from motion_server.control.axis_operations import hold_faulted_axes
from motion_server.control.csp_trajectory_generator import CspTrajectoryGenerator
from motion_server.handlers.command.homing import update_homing_state
from motion_server.handlers.command.jog import stop_jog
from motion_server.handlers.command.axis_state import reset_faults
from motion_server.handlers.command.trajectory import update_active
from motion_server.api.encoder import public_axis_homing_state, public_homing_state


class DriveFaultResponseTest(unittest.TestCase):
    def make_runtime(self, mode="pp"):
        profile = object.__new__(CMMTASDeviceProfile)
        slaves = [SimpleNamespace(
            device_profile=profile,
            rxpdo=SimpleNamespace(
                controlword=0x183F, mode_of_operation=profile.mode_code(mode),
                target_position=500, target_velocity=100, velocity_offset=20,
                has_field=lambda field: True,
            ),
            txpdo=SimpleNamespace(statusword=8 if i == 0 else 0x27,
                                  actual_position=10.0 + i,
                                  mode_of_operation_display=profile.mode_code(mode)),
        ) for i in range(2)]
        generators = [CspTrajectoryGenerator() for _ in slaves]
        for generator in generators:
            generator.command_velocity = 100
            generator.target_position = 500
        def hold(positions, axes):
            positions = list(positions)
            for axis in axes:
                positions[axis] = slaves[axis].txpdo.actual_position
                slaves[axis].rxpdo.target_position = positions[axis]
                generators[axis].reset(positions[axis])
            return positions
        runtime = SimpleNamespace(
            slaves=slaves, hold_axes=Mock(side_effect=hold),
            sync_velocity_command=Mock(), sdo=Mock(), logger=Mock(),
        )
        state = {
            "target_positions": [500, 500], "motion_modes": [mode, mode],
            "motion_mode": mode, "jog_previous_modes": [None, None],
            "homing": {"active": False, "axes": []},
            "trajectory": {"active": False, "axes": []},
        }
        return runtime, state, generators

    def test_all_modes_cancel_only_fault_axis_without_sdo_or_enable(self):
        for mode in ("pp", "pv", "csp", "jog", "homing"):
            with self.subTest(mode=mode):
                runtime, state, generators = self.make_runtime(mode)
                if mode == "jog":
                    state["jog_previous_modes"][0] = "pv"
                if mode == "homing":
                    state["homing"] = {"active": True, "axes": [0],
                                       "original_motion_modes": {0: "csp"}}
                hold_faulted_axes(runtime, state)
                pdo = runtime.slaves[0].rxpdo
                restored = {"jog": "pv", "homing": "csp"}.get(mode, mode)
                self.assertEqual(pdo.mode_of_operation,
                                 runtime.slaves[0].device_profile.mode_code(restored))
                self.assertEqual(state["motion_modes"], [restored, mode])
                self.assertEqual(pdo.controlword, 7)
                self.assertEqual((pdo.target_position, pdo.target_velocity, pdo.velocity_offset),
                                 (10, 0, 0))
                self.assertEqual(generators[0].command_velocity, 0)
                self.assertEqual(generators[1].command_velocity, 100)
                self.assertEqual(runtime.slaves[1].rxpdo.controlword, 0x183F)
                self.assertEqual(runtime.slaves[1].rxpdo.target_position, 500)
                self.assertEqual(runtime.sdo.mock_calls, [])
                if mode == "homing":
                    self.assertFalse(state["homing"]["active"])
                    self.assertEqual(state["homing"]["state"], "fault")

    def test_fault_edge_is_handled_once_and_rearmed_after_clear(self):
        runtime, state, _ = self.make_runtime()
        hold_faulted_axes(runtime, state)
        hold_faulted_axes(runtime, state)
        self.assertEqual(runtime.hold_axes.call_count, 1)
        runtime.slaves[0].txpdo.statusword = 0x40
        hold_faulted_axes(runtime, state)
        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 7)
        runtime.slaves[0].txpdo.statusword = 8
        hold_faulted_axes(runtime, state)
        self.assertEqual(runtime.hold_axes.call_count, 2)

    def test_warning_alone_does_not_cancel_motion(self):
        runtime, state, _ = self.make_runtime()
        runtime.slaves[0].txpdo.statusword = 0xA7
        hold_faulted_axes(runtime, state)
        runtime.hold_axes.assert_not_called()

    def test_fault_reset_leaves_velocity_zero_and_axis_not_enabled(self):
        runtime, state, _ = self.make_runtime("pv")
        hold_faulted_axes(runtime, state)
        with patch("motion_server.handlers.command.axis_state.exchange"):
            reset_faults(runtime, state, [0])
        pdo = runtime.slaves[0].rxpdo
        self.assertEqual(pdo.target_velocity, 0)
        self.assertEqual(pdo.controlword, 7)
        self.assertEqual(state["motion_modes"][0], "pv")

    def test_homing_from_jog_restores_underlying_mode(self):
        runtime, state, _ = self.make_runtime("homing")
        state["homing"] = {"active": True, "axes": [0],
                           "original_motion_modes": {0: "jog"}}
        state["jog_previous_modes"][0] = "pp"
        hold_faulted_axes(runtime, state)
        self.assertEqual(state["motion_modes"][0], "pp")
        self.assertEqual(state["jog_previous_modes"][0], None)

    def test_initial_jog_without_previous_mode_is_cancelled_in_place(self):
        runtime, state, _ = self.make_runtime("jog")
        hold_faulted_axes(runtime, state)
        self.assertEqual(runtime.slaves[0].rxpdo.mode_of_operation, -3)
        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 7)

    def test_absent_velocity_pdo_fields_are_not_added(self):
        runtime, state, _ = self.make_runtime()
        pdo = runtime.slaves[0].rxpdo
        del pdo.target_velocity
        del pdo.velocity_offset
        pdo.has_field = lambda field: field not in {"target_velocity", "velocity_offset"}
        hold_faulted_axes(runtime, state)
        self.assertFalse(hasattr(pdo, "target_velocity"))
        self.assertFalse(hasattr(pdo, "velocity_offset"))

    def test_late_jog_stop_preserves_fault_restored_pv_mode(self):
        runtime, state, _ = self.make_runtime("jog")
        state["jog_previous_modes"][0] = "pv"
        hold_faulted_axes(runtime, state)
        with patch("motion_server.handlers.command.jog.exchange"):
            stop_jog({"cmd": "system/axis/jog_stop", "axis": 0}, runtime, state, None)
        self.assertEqual(state["motion_modes"][0], "pv")
        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 7)
        self.assertEqual(runtime.sdo.mock_calls, [])

    def test_cancelled_homing_axis_is_not_processed_again(self):
        runtime, state, _ = self.make_runtime("homing")
        state["homing"] = {"active": True, "axes": [0, 1],
                           "original_motion_modes": {0: "pp", 1: "pp"}}
        hold_faulted_axes(runtime, state)
        with patch("motion_server.handlers.command.homing.homing_axis_status") as status:
            status.return_value = {"axis": 1, "referenced": False, "homing_error": False}
            update_homing_state(runtime, state)
            status.assert_called_once_with(runtime, 1)
        self.assertEqual(state["motion_modes"], ["pp", "homing"])
        self.assertTrue(state["homing"]["active"])
        self.assertFalse(public_axis_homing_state(state, 0)["active"])
        self.assertNotIn("fault_cancelled_axes", public_homing_state(state))

    def test_trajectory_completion_cannot_reapply_cancelled_axis_target(self):
        runtime, state, _ = self.make_runtime("csp")
        state["trajectory"] = {"active": True, "axes": [0, 1],
                               "points": [{"time_from_start": 1, "positions": [100, 200]}]}
        hold_faulted_axes(runtime, state)
        runtime.trajectory_progress = Mock(return_value={
            "positions": {0: 100, 1: 200}, "elapsed": 1, "active": False, "segment": 0})
        runtime.complete_trajectory = Mock(return_value={1: 200})
        with patch("motion_server.handlers.command.trajectory.log_trajectory_snapshot"), \
             patch("motion_server.handlers.command.trajectory.log_trajectory_debug"):
            update_active(runtime, state)
        runtime.complete_trajectory.assert_called_once_with([1], [200])
        self.assertEqual(state["target_positions"], [10, 200])
        self.assertEqual(state["trajectory"]["state"], "fault")


if __name__ == "__main__":
    unittest.main()
