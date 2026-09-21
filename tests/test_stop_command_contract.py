import unittest
from types import SimpleNamespace

from motion_server.failure import DeviceAccessException, PartialFailure
from motion_server.handlers.command.axis_state import stop_axes


class ReceivePdo:
    def __init__(self, controlword, target_velocity=0, target_velocity_error=None):
        self.controlword = controlword
        self._target_velocity = target_velocity
        self.target_velocity_error = target_velocity_error

    @property
    def target_velocity(self):
        return self._target_velocity

    @target_velocity.setter
    def target_velocity(self, value):
        if self.target_velocity_error is not None:
            raise self.target_velocity_error
        self._target_velocity = value


class StopRuntime:
    def __init__(self, axes):
        self.slaves = axes
        self.logger = SimpleNamespace(status=lambda _message: None)
        self.velocity_commands = {}
        self.synced_trajectory_axes = []
        self.motion_targets = None

    def hold_axes(self, target_positions, axis_indices):
        positions = list(target_positions)
        for axis_index in axis_indices:
            positions[axis_index] = self.slaves[axis_index].txpdo.actual_position
        return positions

    def sync_trajectory_to_actual_position(self, axis_index):
        self.synced_trajectory_axes.append(axis_index)

    def sync_velocity_command(self, axis_index, velocity):
        self.velocity_commands[axis_index] = velocity

    def set_target_positions(self, positions):
        self.motion_targets = list(positions)


def axis(*, enabled, controlword, actual_position, target_velocity=0, error=None):
    return SimpleNamespace(
        txpdo=SimpleNamespace(
            statusword=0x0027 if enabled else 0x0023,
            actual_position=actual_position,
        ),
        rxpdo=ReceivePdo(controlword, target_velocity, error),
    )


def stop_state(modes):
    return {
        "motion_modes": list(modes),
        "target_positions": [100.0 for _ in modes],
        "trajectory": {"active": False},
        "homing": {"active": False},
    }


class StopCommandContractTest(unittest.TestCase):
    def test_mixed_enabled_and_disabled_pv_axes_are_both_stopped(self):
        runtime = StopRuntime(
            [
                axis(
                    enabled=True,
                    controlword=0x000F,
                    actual_position=12.0,
                    target_velocity=250,
                ),
                axis(
                    enabled=False,
                    controlword=0x0007,
                    actual_position=34.0,
                    target_velocity=-300,
                ),
            ]
        )
        state = stop_state(["pv", "pv"])

        result = stop_axes(
            {"cmd": "system/axes/stop", "axes": [0, 1]},
            runtime,
            state,
            {"id": "client"},
        )

        self.assertIsNone(result)
        self.assertEqual(runtime.motion_targets, [12.0, 34.0])
        self.assertEqual(runtime.velocity_commands, {0: 0.0, 1: 0.0})
        self.assertEqual(runtime.slaves[0].rxpdo.target_velocity, 0)
        self.assertEqual(runtime.slaves[1].rxpdo.target_velocity, 0)
        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 0x000F)
        self.assertEqual(runtime.slaves[1].rxpdo.controlword, 0x0007)

    def test_position_and_jog_stop_preserve_disabled_state(self):
        runtime = StopRuntime(
            [
                axis(enabled=True, controlword=0x000F, actual_position=1.0),
                axis(enabled=False, controlword=0x0007, actual_position=2.0),
                axis(
                    enabled=True,
                    controlword=0x183F,
                    actual_position=3.0,
                ),
            ]
        )
        state = stop_state(["pp", "csp", "jog"])

        stop_axes(
            {"cmd": "system/axes/stop", "axes": [0, 1, 2]},
            runtime,
            state,
            {"id": "client"},
        )

        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 0x010F)
        self.assertEqual(runtime.slaves[1].rxpdo.controlword, 0x0007)
        self.assertEqual(runtime.slaves[2].rxpdo.controlword, 0x000F)

    def test_one_device_write_failure_returns_partial_failure(self):
        runtime = StopRuntime(
            [
                axis(
                    enabled=True,
                    controlword=0x000F,
                    actual_position=1.0,
                    target_velocity=100,
                ),
                axis(
                    enabled=False,
                    controlword=0x0007,
                    actual_position=2.0,
                    target_velocity=100,
                    error=OSError("private device detail"),
                ),
            ]
        )

        result = stop_axes(
            {"cmd": "system/axes/stop", "axes": [0, 1]},
            runtime,
            stop_state(["pv", "pv"]),
            {"id": "client"},
        )

        self.assertIsInstance(result, PartialFailure)
        self.assertEqual(result.succeeded, [0])
        self.assertEqual(result.failed[0].target, 1)
        self.assertIsInstance(result.failed[0].exception, DeviceAccessException)

    def test_all_device_writes_failing_raises_device_access_failure(self):
        runtime = StopRuntime(
            [
                axis(
                    enabled=False,
                    controlword=0x0007,
                    actual_position=1.0,
                    error=OSError("private device detail"),
                )
            ]
        )

        with self.assertRaises(DeviceAccessException):
            stop_axes(
                {"cmd": "system/axis/stop", "axis": 0},
                runtime,
                stop_state(["pv"]),
                {"id": "client"},
            )


if __name__ == "__main__":
    unittest.main()
