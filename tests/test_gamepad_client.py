import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest


GAMEPAD_ROOT = Path(__file__).parents[1] / "control_panel" / "gamepad_control_panel"

from control_panel.gamepad_control_panel.config import (  # noqa: E402
    EnableInputConfig,
    load_config,
)
from control_panel.gamepad_control_panel.controller import (  # noqa: E402
    PendantController,
    scaled_deadzone,
)
from control_panel.gamepad_control_panel.input import (  # noqa: E402
    InputSnapshot,
    PygameJoystickAdapter,
)


class FakeClient:
    def __init__(self):
        self.is_connected = True
        self.last_error = ""
        self.messages = []
        self.homing = {"active": False, "state": "complete"}

    def request(self, message, timeout=None):
        self.messages.append(dict(message))
        if message["cmd"] == "system/axes/status":
            return {
                "result": "success",
                "data": {
                    "axis_metadata": [
                        {"motion_kind": "linear"},
                        {"motion_kind": "linear"},
                        {"motion_kind": "linear"},
                        {"motion_kind": "rotary"},
                    ],
                    "motion_limits": [100.0, 1, 1, 0] * 4,
                },
            }
        if message["cmd"] == "system/axis/status":
            return {
                "result": "success",
                "data": {"homing": dict(self.homing)},
            }
        return {"result": "success", "data": {}}

    def start(self):
        pass

    def stop(self):
        pass


class FakeInput:
    def start(self):
        pass

    def stop(self):
        pass

    def snapshot(self):
        return neutral_input()


class FakeJoystick:
    def __init__(self, *, axis_value=0.0, button_value=False):
        self.axis_value = axis_value
        self.button_value = button_value

    def get_axis(self, _index):
        return self.axis_value

    def get_button(self, _index):
        return self.button_value


def neutral_input(**buttons):
    return InputSnapshot(
        sticks={"left_x": 0.0, "left_y": 0.0, "right_x": 0.0, "right_y": 0.0},
        buttons={
            "enable": False,
            "l1": False,
            "r1": False,
            "l3": False,
            "r3": False,
            "cross": False,
            "circle": False,
            "square": False,
            "triangle": False,
            "options": False,
            "create": False,
            "touchpad": False,
            "dpad_up": False,
            "dpad_down": False,
            "dpad_left": False,
            "dpad_right": False,
            **buttons,
        },
        connected=True,
    )


def feedback(statuswords=None):
    return {
        "statuswords": statuswords or [0x0023] * 4,
        "process_data_valid": True,
        "server_health": {"runtime_state": "normal"},
        "command_authority": {
            "owner": 1,
            "owned_by_this_client": True,
            "available": False,
        },
    }


class GamepadClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(GAMEPAD_ROOT / "config.example.json")

    def controller(self):
        client = FakeClient()
        controller = PendantController(self.config, client, FakeInput())
        controller.update_feedback(feedback())
        return controller, client

    def test_scaled_deadzone_uses_remaining_full_range(self):
        self.assertEqual(scaled_deadzone(0.08, 0.08), 0.0)
        self.assertAlmostEqual(scaled_deadzone(0.54, 0.08), 0.5)
        self.assertEqual(scaled_deadzone(-1.0, 0.08), -1.0)

    def test_enable_trigger_requires_release_then_arms_and_release_disables(self):
        controller, client = self.controller()
        controller.tick(neutral_input(enable=True))
        self.assertEqual(controller.state, "Disarmed")
        self.assertNotIn("system/axes/enable", [item["cmd"] for item in client.messages])

        controller.tick(neutral_input())
        controller.tick(neutral_input(enable=True))
        self.assertEqual(controller.state, "Arming")
        self.assertIn("system/axes/enable", [item["cmd"] for item in client.messages])
        mode_commands = [
            item for item in client.messages if item["cmd"] == "system/axis/mode"
        ]
        self.assertEqual([item["axis"] for item in mode_commands], [0, 1, 2, 3])
        self.assertTrue(all(item["mode"] == "pv" for item in mode_commands))

        controller.update_feedback(feedback([0x0027] * 4))
        controller.tick(neutral_input(enable=True))
        self.assertEqual(controller.state, "Armed")

        moving = neutral_input(enable=True)
        moving = replace(moving, sticks={**moving.sticks, "left_x": 1.0})
        controller.tick(moving)
        command = client.messages[-1]
        self.assertEqual(command["cmd"], "system/axes/move_vel")
        self.assertEqual(command["velocities"][0], 10.0)

        controller.tick(neutral_input(enable=True))
        self.assertEqual(client.messages[-1]["cmd"], "system/axes/stop")
        self.assertEqual(controller.state, "Armed")

        controller.tick(neutral_input())
        self.assertEqual(client.messages[-1]["cmd"], "system/axes/disable")
        self.assertEqual(controller.state, "Disarmed")

    def test_single_axis_mode_uses_jog_start_and_stop(self):
        controller, client = self.controller()
        controller.mode = "single"
        controller.tick(neutral_input())
        controller.tick(neutral_input(enable=True))
        controller.update_feedback(feedback([0x0027, 0x0023, 0x0023, 0x0023]))
        controller.tick(neutral_input(enable=True))
        self.assertEqual(controller.state, "Armed")

        moving = replace(
            neutral_input(enable=True),
            sticks={"left_x": 0.0, "left_y": 1.0, "right_x": 0.0, "right_y": 0.0},
        )
        controller.tick(moving)
        self.assertEqual(
            client.messages[-1],
            {
                "cmd": "system/axis/jog_start",
                "axis": 0,
                "direction": "negative",
                "speed": "slow",
            },
        )

        controller.tick(neutral_input(enable=True))
        self.assertEqual(
            client.messages[-1],
            {"cmd": "system/axis/jog_stop", "axis": 0},
        )
        self.assertNotIn(
            "system/axis/move_vel",
            [message["cmd"] for message in client.messages],
        )

    def test_single_axis_jog_direction_is_same_for_y_and_z(self):
        for selected_axis in (1, 2):
            for stick_y, expected_direction in ((-1.0, "positive"), (1.0, "negative")):
                with self.subTest(axis=selected_axis, stick_y=stick_y):
                    controller, client = self.controller()
                    controller.mode = "single"
                    controller.selected_axis = selected_axis
                    controller.state = "Armed"
                    words = [0x0023] * 4
                    words[selected_axis] = 0x0027
                    controller.update_feedback(feedback(words))

                    moving = replace(
                        neutral_input(enable=True),
                        sticks={
                            "left_x": 0.0,
                            "left_y": stick_y,
                            "right_x": 0.0,
                            "right_y": 0.0,
                        },
                    )
                    controller.tick(moving)

                    self.assertEqual(
                        client.messages[-1],
                        {
                            "cmd": "system/axis/jog_start",
                            "axis": selected_axis,
                            "direction": expected_direction,
                            "speed": "slow",
                        },
                    )

    def test_multi_axis_uses_configured_logical_stick_mapping(self):
        controller, client = self.controller()
        controller.config = replace(
            self.config,
            axis_inputs={
                "x": "right_x",
                "y": "left_y",
                "z": "right_y",
                "rotation": "left_x",
            },
        )
        controller.state = "Armed"
        controller.update_feedback(feedback([0x0027] * 4))
        self.assertTrue(controller._validate_axis_contract())
        moving = replace(
            neutral_input(enable=True),
            sticks={"left_x": 0.0, "left_y": 0.0, "right_x": 1.0, "right_y": 0.0},
        )

        controller.tick(moving)

        self.assertEqual(client.messages[-1]["cmd"], "system/axes/move_vel")
        self.assertEqual(client.messages[-1]["velocities"], [10.0, 0.0, 0.0, 0.0])

    def test_cross_starts_homing_only_in_single_mode(self):
        controller, client = self.controller()
        controller.tick(neutral_input())
        controller.tick(neutral_input(cross=True))
        self.assertNotIn(
            "system/axis/home",
            [message["cmd"] for message in client.messages],
        )
        self.assertEqual(controller.last_notice, "Homing rejected: Single mode only")

        controller.mode = "single"
        controller.tick(neutral_input())
        controller.tick(neutral_input(enable=True))
        controller.update_feedback(feedback([0x0027, 0x0023, 0x0023, 0x0023]))
        controller.tick(neutral_input(enable=True))
        self.assertEqual(controller.state, "Armed")

        controller.tick(neutral_input(enable=True, cross=True))
        self.assertIn(
            {"cmd": "system/axis/home", "axis": 0},
            client.messages,
        )
        self.assertEqual(controller.state, "Armed")
        self.assertEqual(controller.last_notice, "Homing complete: Axis 0")

    def test_homing_requires_neutral_standstill(self):
        controller, client = self.controller()
        controller.mode = "single"
        controller.state = "Armed"
        controller.update_feedback(feedback([0x0127, 0x0023, 0x0023, 0x0023]))

        controller.tick(neutral_input(enable=True, cross=True))

        self.assertNotIn(
            "system/axis/home",
            [message["cmd"] for message in client.messages],
        )
        self.assertIn("Standstill", controller.last_notice)

    def test_homing_blocks_jog_and_enable_release_disables(self):
        controller, client = self.controller()
        client.homing = {"active": True, "state": "running"}
        controller.mode = "single"
        controller.state = "Armed"
        controller._enable_released_since_connect = True
        controller.update_feedback(feedback([0x0027, 0x0023, 0x0023, 0x0023]))

        controller.tick(neutral_input(enable=True, cross=True))
        self.assertEqual(controller.state, "Homing")

        moving = replace(
            neutral_input(enable=True),
            sticks={"left_x": 0.0, "left_y": 1.0, "right_x": 0.0, "right_y": 0.0},
        )
        controller.tick(moving)
        self.assertNotIn(
            "system/axis/jog_start",
            [message["cmd"] for message in client.messages],
        )

        controller.tick(neutral_input())
        self.assertEqual(controller.state, "Disarmed")
        self.assertEqual(client.messages[-1]["cmd"], "system/axis/disable")

    def test_mode_change_requires_disarmed_neutral_standstill(self):
        controller, _client = self.controller()
        controller.tick(neutral_input())
        controller.tick(neutral_input(touchpad=True))
        self.assertEqual(controller.mode, "single")

        controller.state = "Armed"
        controller.update_feedback(feedback([0x0027] * 4))
        controller.tick(neutral_input(enable=True))
        controller.tick(neutral_input(enable=True, touchpad=True))
        self.assertEqual(controller.mode, "single")

    def test_authority_release_does_not_disable_axes_first(self):
        controller, client = self.controller()
        controller.tick(neutral_input())
        controller.tick(neutral_input(options=True))

        commands = [message["cmd"] for message in client.messages]
        self.assertIn("system/authority/release", commands)
        self.assertNotIn("system/axes/disable", commands)

    def test_authority_and_mode_actions_can_be_remapped(self):
        controller, client = self.controller()
        controller.config = replace(
            self.config,
            actions={
                **self.config.actions,
                "authority_toggle": "r1",
                "mode_toggle": "r3",
            },
        )
        controller.tick(neutral_input())
        controller.tick(neutral_input(r1=True))
        self.assertIn(
            "system/authority/release",
            [message["cmd"] for message in client.messages],
        )

        controller.update_feedback(feedback())
        controller.tick(neutral_input())
        controller.tick(neutral_input(r3=True))
        self.assertEqual(controller.mode, "single")

    def test_speed_scale_can_change_while_armed(self):
        controller, _client = self.controller()
        controller.state = "Armed"
        controller.update_feedback(feedback([0x0027] * 4))
        before = controller.scale_index

        snapshot = neutral_input(enable=True, dpad_up=True)
        controller.tick(snapshot)

        self.assertEqual(controller.scale_index, before + 1)

    def test_input_initialization_and_recovery_do_not_leave_stale_error(self):
        controller, _client = self.controller()

        controller.tick(InputSnapshot())
        self.assertEqual(controller.last_error, "")

        controller.tick(InputSnapshot(error="Configured gamepad was not found"))
        self.assertEqual(controller.last_error, "Configured gamepad was not found")

        controller.tick(neutral_input())
        self.assertEqual(controller.last_error, "")

    def test_axis_contract_error_clears_after_valid_recheck(self):
        controller, _client = self.controller()
        controller.config = replace(
            self.config,
            server_axes={**self.config.server_axes, "rotation": 4},
        )
        self.assertFalse(controller._validate_axis_contract())
        self.assertIn("outside server topology", controller.last_error)

        controller.config = self.config
        controller.axis_contract = None
        self.assertTrue(controller._validate_axis_contract())
        self.assertEqual(controller.last_error, "")

    def test_config_rejects_duplicate_axis_indices(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        value["server"]["axes"]["rotation"] = value["server"]["axes"]["x"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                load_config(path)

    def test_config_rejects_duplicate_logical_stick_assignments(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        value["axes"]["rotation"] = value["axes"]["x"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "logical stick input"):
                load_config(path)

    def test_dualsense_enable_input_is_configured_as_l2_axis(self):
        raw = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertNotIn("mapping", raw["device"])
        self.assertEqual(raw["device"]["profile"], "dualsense_windows")
        self.assertEqual(self.config.device_profile, "dualsense_windows")
        mapping = self.config.enable_input
        self.assertEqual(
            {name: self.config.buttons[name] for name in ("l1", "r1", "l3", "r3")},
            {"l1": 9, "r1": 10, "l3": 7, "r3": 8},
        )
        self.assertEqual(self.config.trigger_axes, {"l2": 4, "r2": 5})
        self.assertEqual(mapping.control, "l2")
        self.assertEqual(mapping.source, "axis")
        self.assertEqual(mapping.index, 4)
        self.assertEqual(mapping.threshold, 0.5)
        self.assertEqual(mapping.pressed_when, "above")
        self.assertEqual(self.config.actions["homing"], "cross")

    def test_enable_input_can_be_mapped_to_a_button(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        value["actions"]["enable"] = {
            "control": "l1",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config.enable_input.source, "button")
        self.assertEqual(config.enable_input.index, 9)

    def test_enable_input_adapter_applies_axis_threshold_or_button(self):
        adapter = PygameJoystickAdapter(self.config)
        self.assertFalse(adapter._read_enable_input(FakeJoystick(axis_value=0.49)))
        self.assertTrue(adapter._read_enable_input(FakeJoystick(axis_value=0.5)))

        button_config = replace(
            self.config,
            enable_input=EnableInputConfig(
                control="l1", source="button", index=9
            ),
        )
        adapter = PygameJoystickAdapter(button_config)
        self.assertTrue(adapter._read_enable_input(FakeJoystick(button_value=True)))

    def test_unknown_device_profile_is_rejected(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        value["device"]["profile"] = "missing_profile"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown gamepad device profile"):
                load_config(path)

    def test_homing_input_can_be_assigned_to_an_available_button(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        value["actions"]["homing"] = "l3"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config.actions["homing"], "l3")

        controller, client = self.controller()
        controller.config = config
        controller.mode = "single"
        controller.state = "Armed"
        controller.update_feedback(feedback([0x0027, 0x0023, 0x0023, 0x0023]))
        controller.tick(neutral_input(enable=True, l3=True))
        self.assertIn(
            {"cmd": "system/axis/home", "axis": 0},
            client.messages,
        )

    def test_actions_reject_duplicate_or_enable_control(self):
        value = json.loads((GAMEPAD_ROOT / "config.example.json").read_text(encoding="utf-8"))
        for control in ("square", "l2"):
            with self.subTest(control=control), tempfile.TemporaryDirectory() as directory:
                value["actions"]["homing"] = control
                path = Path(directory) / "config.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "actions"):
                    load_config(path)


if __name__ == "__main__":
    unittest.main()
