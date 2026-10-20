from dataclasses import dataclass
import queue
import threading
import time


ROLE_STICKS = {
    "x": "left_x",
    "y": "left_y",
    "z": "right_y",
    "rotation": "right_x",
}
OPERATION_ENABLED_MASK = 0x006F
OPERATION_ENABLED_STATUS = 0x0027
MOVING_BIT = 1 << 8
FAULT_BIT = 1 << 3


@dataclass(frozen=True)
class PendantStatus:
    state: str
    mode: str
    selected_axis: int
    speed_scale: float
    authority: str
    last_error: str
    last_notice: str


class PendantController:
    def __init__(self, config, client, input_adapter):
        self.config = config
        self.client = client
        self.input = input_adapter
        self.state = "Disconnected"
        self.mode = "multi"
        self.selected_axis = next(iter(config.server_axes.values()))
        self.scale_index = config.speed_scales.index(config.speed_scale_default)
        self.feedback = {}
        self.axis_contract = None
        self.last_error = ""
        self.last_notice = ""
        self._previous_buttons = {}
        self._enable_released_since_connect = False
        self._neutral_stop_sent = False
        self._input_error_active = False
        self._axis_contract_error_active = False
        self._active_jog = None
        self._homing_axis = None
        self._next_homing_poll = 0.0
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.RLock()

    def start(self):
        self.input.start()
        self.client.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="gamepad-control", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.config.request_timeout + 1.0)
        self.input.stop()
        self.client.stop()

    def update_feedback(self, message):
        with self._lock:
            self.feedback = dict(message)

    def status(self):
        with self._lock:
            authority = self.feedback.get("command_authority", {})
            owner = authority.get("owner")
            authority_text = "Owned" if authority.get("owned_by_this_client") else (
                "Available" if authority.get("available") else f"Owner {owner}"
            )
            return PendantStatus(
                state=self.state,
                mode=self.mode,
                selected_axis=self.selected_axis,
                speed_scale=self.config.speed_scales[self.scale_index],
                authority=authority_text,
                last_error=self.last_error,
                last_notice=self.last_notice,
            )

    def tick(self, snapshot=None):
        snapshot = snapshot or self.input.snapshot()
        with self._lock:
            if not self.client.is_connected:
                self._set_disarmed("Disconnected")
                self._remember_inputs(snapshot)
                return
            if self.state == "Disconnected":
                self.state = "Disarmed"
                self._enable_released_since_connect = False
                self.axis_contract = None
                if self._axis_contract_error_active:
                    self.last_error = ""
                    self._axis_contract_error_active = False

            if not snapshot.connected:
                if snapshot.error:
                    self.last_error = snapshot.error
                    self._input_error_active = True
                self._remember_inputs(snapshot)
                return
            if self._input_error_active:
                self.last_error = ""
                self._input_error_active = False

            neutral = sticks_neutral(snapshot.sticks, self.config.deadzone)
            enable_held = bool(snapshot.buttons.get("enable", False))
            if not enable_held and neutral:
                self._enable_released_since_connect = True

            self._handle_edges(snapshot, neutral)
            if self.state == "Homing":
                if not enable_held:
                    self._disable_mapped("Enable trigger released during Homing")
                elif not self._armed_feedback_is_safe():
                    self._disable_mapped("Authority, Axis, or server state was lost during Homing")
                else:
                    self._poll_homing()
            elif self.state == "Armed":
                if not enable_held:
                    self._disable_mapped("Enable trigger released")
                elif not self._armed_feedback_is_safe():
                    self._disable_mapped("Authority, Axis, or server state was lost")
                elif self.mode == "single":
                    self._drive_single_axis_jog(snapshot, neutral)
                elif neutral:
                    if not self._neutral_stop_sent:
                        if self._request(self._axes_message("stop")) is None:
                            self._disable_mapped("Stop failed")
                        else:
                            self._neutral_stop_sent = True
                else:
                    self._neutral_stop_sent = False
                    if self._request(self._velocity_message(snapshot)) is None:
                        self._disable_mapped("Velocity command failed")
            elif self.state == "Arming":
                if not enable_held:
                    self._disable_mapped("Enable trigger released while arming")
                elif self._mapped_axes_enabled():
                    self.state = "Armed"
                    self.last_notice = "Armed"

            self._remember_inputs(snapshot)

    def _run(self):
        next_tick = time.monotonic()
        while not self._stop.is_set():
            self._drain_feedback()
            self.tick()
            next_tick += self.config.update_period
            delay = next_tick - time.monotonic()
            if delay <= 0.0:
                next_tick = time.monotonic()
                continue
            self._stop.wait(delay)

    def _drain_feedback(self):
        while True:
            try:
                message = self.client.get_feedback(timeout=0.0)
            except queue.Empty:
                return
            self.update_feedback(message)

    def _handle_edges(self, snapshot, neutral):
        rising = {
            name
            for name, pressed in snapshot.buttons.items()
            if pressed and not self._previous_buttons.get(name, False)
        }
        enable_rising = "enable" in rising
        action = lambda name: self.config.actions[name] in rising
        if action("authority_toggle"):
            self._toggle_authority()
            return
        if action("fault_reset"):
            self._request(self._axes_message("fault_reset"))
        elif action("stop"):
            self._request(self._axes_message("stop"))
            self._active_jog = None
        elif action("all_axes_stop"):
            self._request({"cmd": "system/axes/stop", "axes": self._all_axes()})
            self._active_jog = None
        elif action("homing"):
            self._start_homing(neutral)
        if self.mode == "multi":
            if action("speed_up"):
                self.scale_index = min(self.scale_index + 1, len(self.config.speed_scales) - 1)
            elif action("speed_down"):
                self.scale_index = max(self.scale_index - 1, 0)
        if self.state in {"Arming", "Armed", "Homing", "Releasing"}:
            return
        if action("mode_toggle"):
            if self._transition_allowed(neutral):
                self.mode = "single" if self.mode == "multi" else "multi"
                self.last_notice = f"Mode changed to {self.mode}"
            else:
                self.last_notice = "Mode change rejected: require Disarmed, neutral, Standstill"
        axis_direction = int(action("next_axis")) - int(action("previous_axis"))
        if self.mode == "single" and axis_direction != 0:
            if self._transition_allowed(neutral):
                self._select_axis(axis_direction)
            else:
                self.last_notice = "Axis change rejected: require Disarmed, neutral, Standstill"
        if enable_rising:
            self._arm(neutral)

    def _arm(self, neutral):
        if not self._enable_released_since_connect:
            self.last_notice = "Arm rejected: release Enable trigger at neutral after connection"
            return
        if not self._owns_authority() or not neutral or not self._all_axes_standstill():
            self.last_notice = "Arm rejected: require authority, neutral, all-Axis Standstill"
            return
        if not self._validate_axis_contract():
            return
        self.state = "Arming"
        if self.mode == "multi" and not self._set_mapped_axes_pv():
            self._disable_mapped("PV mode change failed")
            return
        if self._request(self._axes_message("enable")) is None:
            self._disable_mapped("Enable failed")

    def _toggle_authority(self):
        if self._owns_authority():
            self.state = "Releasing"
            response = self._request({"cmd": "system/authority/release"})
            self.state = "Disarmed"
            if response is None:
                self.last_error = "Authority release failed"
        elif self.feedback.get("command_authority", {}).get("available", False):
            self._request({"cmd": "system/authority/request"})

    def _start_homing(self, neutral):
        if self.mode != "single":
            self.last_notice = "Homing rejected: Single mode only"
            return
        if self.state != "Armed":
            self.last_notice = "Homing rejected: require Single mode Armed"
            return
        if not neutral or self._active_jog is not None or not self._all_axes_standstill():
            self.last_notice = "Homing rejected: require neutral and all-Axis Standstill"
            return
        axis_index = self.selected_axis
        response = self._request({"cmd": "system/axis/home", "axis": axis_index})
        if response is None:
            self._disable_mapped("Homing command failed")
            return
        self._homing_axis = axis_index
        self._next_homing_poll = 0.0
        self.state = "Homing"
        self.last_notice = f"Homing Axis {axis_index}"

    def _poll_homing(self):
        now = time.monotonic()
        if now < self._next_homing_poll:
            return
        self._next_homing_poll = now + 0.2
        response = self._request(
            {"cmd": "system/axis/status", "axis": self._homing_axis}
        )
        if response is None:
            self._disable_mapped("Homing status failed")
            return
        homing = response.get("data", {}).get("homing", {})
        if homing.get("active", False):
            return
        result = homing.get("state", "unknown")
        axis_index = self._homing_axis
        self._homing_axis = None
        if result == "complete":
            self.state = "Armed"
            self.last_notice = f"Homing complete: Axis {axis_index}"
            return
        self._disable_mapped(f"Homing ended: {result}")

    def _disable_mapped(self, reason):
        self.state = "Disarmed"
        self._neutral_stop_sent = False
        self._active_jog = None
        self._homing_axis = None
        if self.client.is_connected and self._owns_authority():
            self._request(self._axes_message("disable"))
        self.last_notice = reason

    def _request(self, message):
        try:
            response = self.client.request(message, timeout=self.config.request_timeout)
        except Exception as exc:
            self.last_error = str(exc)
            return None
        if response.get("result") != "success":
            failure = response.get("failure", {})
            self.last_error = f"{failure.get('code', 'FAILED')}: {failure.get('message', '')}"
            return None
        self.last_error = ""
        return response

    def _axes_message(self, action):
        axes = self._mapped_axes()
        command = "system/axis" if len(axes) == 1 else "system/axes"
        message = {"cmd": f"{command}/{action}"}
        message["axis" if len(axes) == 1 else "axes"] = axes[0] if len(axes) == 1 else axes
        return message

    def _velocity_message(self, snapshot):
        axes = self._mapped_axes()
        velocities = [
            self._role_velocity(
                role,
                snapshot.sticks.get(self.config.axis_inputs[role], 0.0),
            )
            for role in self.config.server_axes
        ]
        return {"cmd": "system/axes/move_vel", "axes": axes, "velocities": velocities}

    def _set_mapped_axes_pv(self):
        for axis_index in self._mapped_axes():
            if self._request(
                {"cmd": "system/axis/mode", "axis": axis_index, "mode": "pv"}
            ) is None:
                return False
        return True

    def _drive_single_axis_jog(self, snapshot, _neutral):
        axis_index = self.selected_axis
        value = float(snapshot.sticks.get("left_y", 0.0))
        if abs(value) <= self.config.deadzone:
            if self._active_jog is not None:
                if self._request(
                    {"cmd": "system/axis/jog_stop", "axis": axis_index}
                ) is None:
                    self._disable_mapped("Jog stop failed")
                    return
                self._active_jog = None
            return

        direction = "negative" if value > 0.0 else "positive"
        requested_jog = (axis_index, direction, "slow")
        if requested_jog == self._active_jog:
            return
        if self._active_jog is not None:
            if self._request(
                {"cmd": "system/axis/jog_stop", "axis": self._active_jog[0]}
            ) is None:
                self._disable_mapped("Jog direction change failed")
                return
        if self._request(
            {
                "cmd": "system/axis/jog_start",
                "axis": axis_index,
                "direction": direction,
                "speed": "slow",
            }
        ) is None:
            self._disable_mapped("Jog command failed")
            return
        self._active_jog = requested_jog

    def _role_velocity(self, role, raw_value):
        value = scaled_deadzone(raw_value, self.config.deadzone)
        if self.config.invert[role]:
            value = -value
        axis_index = self.config.server_axes[role]
        maximum = float(self.axis_contract["motion_limits"][axis_index * 4])
        scale = self.config.speed_scales[self.scale_index]
        return max(-maximum, min(maximum, value * maximum * scale))

    def _mapped_axes(self):
        return (
            [self.selected_axis]
            if self.mode == "single"
            else list(self.config.server_axes.values())
        )

    def _all_axes(self):
        return list(range(len(self.feedback.get("statuswords", []))))

    def _select_axis(self, direction):
        axes = list(self.config.server_axes.values())
        index = axes.index(self.selected_axis)
        self.selected_axis = axes[(index + (1 if direction > 0 else -1)) % len(axes)]
        self.last_notice = f"Selected Axis {self.selected_axis}"

    def _transition_allowed(self, neutral):
        return self.state == "Disarmed" and neutral and self._all_axes_standstill()

    def _owns_authority(self):
        return bool(self.feedback.get("command_authority", {}).get("owned_by_this_client"))

    def _all_axes_standstill(self):
        statuswords = self.feedback.get("statuswords", [])
        return bool(statuswords) and all(not int(value) & MOVING_BIT for value in statuswords)

    def _mapped_axes_enabled(self):
        statuswords = self.feedback.get("statuswords", [])
        return all(
            axis < len(statuswords)
            and int(statuswords[axis]) & OPERATION_ENABLED_MASK == OPERATION_ENABLED_STATUS
            for axis in self._mapped_axes()
        )

    def _armed_feedback_is_safe(self):
        health = self.feedback.get("server_health", {})
        statuswords = self.feedback.get("statuswords", [])
        return (
            self._owns_authority()
            and bool(self.feedback.get("process_data_valid", False))
            and health.get("runtime_state", "normal") == "normal"
            and self._mapped_axes_enabled()
            and all(not int(statuswords[axis]) & FAULT_BIT for axis in self._mapped_axes())
        )

    def _validate_axis_contract(self):
        if self.axis_contract is None:
            response = self._request({"cmd": "system/axes/status"})
            if response is None:
                return False
            self.axis_contract = response.get("data", {})
        metadata = self.axis_contract.get("axis_metadata", [])
        limits = self.axis_contract.get("motion_limits", [])
        axis_count = len(self.feedback.get("statuswords", []))
        for role, axis_index in self.config.server_axes.items():
            if axis_index >= axis_count:
                self.last_error = f"Configured {role} Axis {axis_index} is outside server topology"
                self._axis_contract_error_active = True
                return False
            expected = "rotary" if role == "rotation" else "linear"
            kind = metadata[axis_index].get("motion_kind") if axis_index < len(metadata) else None
            if kind != expected:
                self.last_error = f"Configured {role} requires server Axis kind {expected}"
                self._axis_contract_error_active = True
                return False
            limit_index = axis_index * 4
            if limit_index >= len(limits) or float(limits[limit_index]) <= 0.0:
                self.last_error = f"Server {role} max velocity is missing or invalid"
                self._axis_contract_error_active = True
                return False
        if self._axis_contract_error_active:
            self.last_error = ""
            self._axis_contract_error_active = False
        return True

    def _set_disarmed(self, state):
        self.state = state
        self._neutral_stop_sent = False

    def _remember_inputs(self, snapshot):
        self._previous_buttons = dict(snapshot.buttons)


def scaled_deadzone(value, deadzone):
    value = max(-1.0, min(1.0, float(value)))
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return scaled if value > 0.0 else -scaled


def sticks_neutral(sticks, deadzone):
    return all(abs(float(sticks.get(name, 0.0))) <= deadzone for name in ROLE_STICKS.values())
