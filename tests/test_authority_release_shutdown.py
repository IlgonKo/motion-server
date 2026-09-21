import json
import unittest
from types import SimpleNamespace

from motion_server.api.deferred import DeferredResponse
from motion_server.app.client_transport import close_client
from motion_server.diagnostic import DiagnosticManager
from motion_server.failure import PartialFailure
from motion_server.app.authority_release import (
    begin_authority_release,
    process_pending_authority_release,
)


class Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Runtime:
    def __init__(self, statuswords):
        self.slaves = [
            SimpleNamespace(
                txpdo=SimpleNamespace(statusword=value, actual_position=float(index + 1)),
                rxpdo=SimpleNamespace(controlword=0x000F, target_velocity=100),
            )
            for index, value in enumerate(statuswords)
        ]
        self.logger = SimpleNamespace(status=lambda _message: None)
        self.velocity_commands = {}

    def hold_axes(self, positions, axes):
        held = list(positions)
        for axis_index in axes:
            held[axis_index] = self.slaves[axis_index].txpdo.actual_position
        return held

    def sync_trajectory_to_actual_position(self, _axis_index):
        pass

    def sync_velocity_command(self, axis_index, velocity):
        self.velocity_commands[axis_index] = velocity

    def set_target_positions(self, positions):
        self.target_positions = list(positions)


def client(client_id=1):
    return {
        "id": client_id,
        "conn": Connection(),
        "output_buffer": bytearray(),
    }


def state(owner=1, axis_count=2):
    return {
        "command_authority_owner": owner,
        "authority_release": None,
        "motion_modes": ["pv"] * axis_count,
        "target_positions": [100.0] * axis_count,
        "trajectory": {"active": False},
        "homing": {"active": False},
        "diagnostic_manager": DiagnosticManager(),
    }


def buffered_response(active_client):
    return json.loads(bytes(active_client["output_buffer"]).decode("utf-8"))


class AuthorityReleaseShutdownTest(unittest.TestCase):
    def test_release_waits_for_all_axes_standstill_and_keeps_owner(self):
        runtime = Runtime([0x0127, 0x0027])
        active_client = client()
        active_state = state()

        result = begin_authority_release(
            {"cmd": "system/authority/release", "request_id": "release-1"},
            active_client,
            active_state,
            runtime,
        )

        self.assertIsInstance(result, DeferredResponse)
        self.assertEqual(active_state["command_authority_owner"], 1)
        self.assertEqual(active_state["authority_release"]["phase"], "releasing")
        self.assertEqual(runtime.velocity_commands, {0: 0.0, 1: 0.0})
        self.assertFalse(process_pending_authority_release(runtime, active_state))

        runtime.slaves[0].txpdo.statusword = 0x0027
        self.assertTrue(process_pending_authority_release(runtime, active_state))

        response = buffered_response(active_client)
        self.assertEqual(response["result"], "success")
        self.assertEqual(response["request_id"], "release-1")
        self.assertEqual(response["data"]["release_mode"], "controlled_stop")
        self.assertIsNone(active_state["command_authority_owner"])

    def test_release_timeout_disables_all_axes_then_releases(self):
        runtime = Runtime([0x0127, 0x0127])
        active_client = client()
        active_state = state()

        begin_authority_release(
            {"cmd": "system/authority/release"},
            active_client,
            active_state,
            runtime,
        )
        deadline = active_state["authority_release"]["deadline"]

        self.assertTrue(
            process_pending_authority_release(
                runtime,
                active_state,
                now=deadline,
            )
        )

        response = buffered_response(active_client)
        self.assertEqual(response["result"], "success")
        self.assertEqual(response["data"]["release_mode"], "quick_stop_fallback")
        self.assertEqual(response["data"]["fallback_reason"], "standstill_timeout")
        self.assertEqual(
            [slave.rxpdo.controlword for slave in runtime.slaves],
            [0x0007, 0x0007],
        )
        self.assertIsNone(active_state["command_authority_owner"])

    def test_owner_disconnect_quick_stops_all_axes_and_releases(self):
        runtime = Runtime([0x0127, 0x0027])
        active_client = client()
        active_state = state()

        close_client(active_client, runtime, active_state)

        self.assertTrue(active_client["conn"].closed)
        self.assertEqual(
            [slave.rxpdo.controlword for slave in runtime.slaves],
            [0x0007, 0x0007],
        )
        self.assertIsNone(active_state["command_authority_owner"])

    def test_non_owner_disconnect_does_not_change_motion(self):
        runtime = Runtime([0x0127])
        other_client = client(2)
        active_state = state(axis_count=1)

        close_client(other_client, runtime, active_state)

        self.assertEqual(runtime.slaves[0].rxpdo.controlword, 0x000F)
        self.assertEqual(active_state["command_authority_owner"], 1)

    def test_stop_and_fallback_partial_failure_retains_authority(self):
        class FailingVelocityPdo:
            controlword = 0x000F

            @property
            def target_velocity(self):
                return 100

            @target_velocity.setter
            def target_velocity(self, _value):
                raise OSError("target write failed")

        runtime = Runtime([0x0127, 0x0127])
        runtime.slaves[1].rxpdo = FailingVelocityPdo()
        active_state = state()

        result = begin_authority_release(
            {"cmd": "system/authority/release"},
            client(),
            active_state,
            runtime,
        )

        self.assertIsInstance(result, PartialFailure)
        self.assertEqual(active_state["command_authority_owner"], 1)
        self.assertEqual(active_state["authority_release"]["phase"], "failed")
        self.assertEqual(runtime.slaves[1].rxpdo.controlword, 0x0007)


if __name__ == "__main__":
    unittest.main()
