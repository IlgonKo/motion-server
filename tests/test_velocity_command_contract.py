import unittest
from unittest.mock import patch

from configuration import CspInterpolationMode
from configuration.bus import DeviceRole
from configuration.models import (
    BackendType,
    BusDeviceConfig,
    CmmtDeviceConfig,
    CommandLogConfig,
    CspCommandStepLogConfig,
    CspProfile,
    CycleConfig,
    CycleStatsLogConfig,
    DistributedClockConfig,
    EtherCATConfig,
    LoggingConfig,
    MotionConfig,
    PositionFeedbackLagLogConfig,
    PreLoggingConfig,
    StatusLogConfig,
    TrajectoryLogConfig,
    VelocityAnomalyLogConfig,
)
from device.cmmt.non_pdo_configuration import CMMT_NON_PDO_CONFIGURATIONS
from motion_server.app.startup import create_axis_runtime, refresh_axis_parameter_cache
from motion_server.control.setpoint_output import command_profile_velocities
from motion_server.failure import LimitViolationException


class VelocityCommandContractTest(unittest.TestCase):
    def test_move_vel_accepts_mixed_linear_and_rotary_axes(self):
        runtime, state = self._runtime_state()

        command_profile_velocities(
            runtime,
            state,
            [0, 1],
            [10, 10000],
            "system/axes/move_vel",
            None,
        )

        self.assertEqual(runtime.slaves[0].rxpdo.target_velocity, 10)
        self.assertEqual(runtime.slaves[1].rxpdo.target_velocity, 10000)
        self.assertEqual(state["motion_modes"], ["pv", "pv"])

    def test_move_vel_rejects_velocity_above_axis_motion_limit(self):
        runtime, state = self._runtime_state()

        with self.assertRaises(LimitViolationException) as context:
            command_profile_velocities(
                runtime,
                state,
                [0],
                [101],
                "system/axis/move_vel",
                None,
            )

        self.assertEqual(context.exception.field, "axis 0 target_velocity")
        self.assertEqual(context.exception.maximum, 100.0)

    def test_move_vel_validates_pdo_fields_before_writing_any_axis(self):
        runtime, state = self._runtime_state()

        def require_fields(runtime_value, mode_name, axis_index):
            if axis_index == 1:
                raise RuntimeError("axis 1 target_velocity missing")

        with patch(
            "motion_server.control.setpoint_output.require_pdo_fields_for_mode",
            side_effect=require_fields,
        ):
            with self.assertRaisesRegex(RuntimeError, "axis 1 target_velocity missing"):
                command_profile_velocities(
                    runtime,
                    state,
                    [0, 1],
                    [10, 10000],
                    "system/axes/move_vel",
                    None,
                )

        self.assertEqual(runtime.slaves[0].rxpdo.target_velocity, 0)
        self.assertEqual(runtime.slaves[1].rxpdo.target_velocity, 0)
        self.assertEqual(state["motion_modes"], ["pp", "pp"])

    def test_linear_axis_metadata_marks_velocity_mode_available(self):
        runtime, _state = self._runtime_state()

        metadata = runtime.device_manager.axes.unit_metadata()

        self.assertEqual(metadata[0]["motion_kind"], "linear")
        self.assertTrue(metadata[0]["pv_allowed"])
        self.assertEqual(metadata[0]["velocity_unit"], "mm/s")
        self.assertEqual(metadata[1]["motion_kind"], "rotary")
        self.assertTrue(metadata[1]["pv_allowed"])
        self.assertEqual(metadata[1]["velocity_unit"], "deg/s")

    @staticmethod
    def _runtime_state():
        runtime = create_axis_runtime(
            EtherCATConfig(
                BackendType.MOCK,
                "",
                None,
                CycleConfig(0.01, 0.0),
                DistributedClockConfig(
                    False,
                    0,
                    False,
                    False,
                    0,
                    0.0,
                    0.0,
                    0.0,
                ),
            ),
            MotionConfig(
                "pp",
                CspProfile.QUINTIC,
                100000.0,
                CspInterpolationMode.CSP,
                False,
            ),
            LoggingConfig(
                CommandLogConfig(False),
                StatusLogConfig(False, 1.0),
                CycleStatsLogConfig(False, 1.0),
                TrajectoryLogConfig(False, False),
                VelocityAnomalyLogConfig(False, 0.0, 0.0, 1.0),
                PositionFeedbackLagLogConfig(False, 1.0),
                CspCommandStepLogConfig(False, 0.0, 0.0),
                PreLoggingConfig(False, 0),
            ),
            (
                BusDeviceConfig(
                    0,
                    DeviceRole.AXIS,
                    "cmmt_as",
                    None,
                    CmmtDeviceConfig(
                        "cmmt_as",
                        0,
                        "motion_server_default",
                        CMMT_NON_PDO_CONFIGURATIONS["linear_mm"],
                    ),
                ),
                BusDeviceConfig(
                    1,
                    DeviceRole.AXIS,
                    "cmmt_as",
                    None,
                    CmmtDeviceConfig(
                        "cmmt_as",
                        1,
                        "motion_server_default",
                        CMMT_NON_PDO_CONFIGURATIONS["rotary_deg"],
                    ),
                ),
            ),
        )
        runtime.connect(target_state="preop")
        runtime.enter_operational()
        for axis_index in range(2):
            refresh_axis_parameter_cache(runtime, axis_index)
        runtime.device_manager.axes.configure_unit_conversion(
            runtime.axis_parameters.user_position_units,
            runtime.axis_parameters.converting_unit_exponents,
        )
        for slave in runtime.slaves:
            slave.txpdo.statusword = 0x0027
        runtime.set_axis_motion_limits(0, 100, 1000, 1000, 1)
        runtime.set_axis_motion_limits(1, 50, 1000, 1000, 1)
        return runtime, {
            "axis_devices": runtime.device_manager.axes,
            "motion_modes": ["pp", "pp"],
            "target_positions": [0, 0],
        }


if __name__ == "__main__":
    unittest.main()
