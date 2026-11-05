from dataclasses import dataclass, field
import os
import threading
import time

from control_panel.gamepad_control_panel.machine_state import (
    MachineOutputIntent,
    MachineState,
)


@dataclass(frozen=True)
class InputSnapshot:
    sticks: dict[str, float] = field(default_factory=dict)
    buttons: dict[str, bool] = field(default_factory=dict)
    hat: tuple[int, int] = (0, 0)
    connected: bool = False
    name: str = ""
    guid: str = ""
    error: str = ""


@dataclass(frozen=True)
class OutputStatus:
    state: str = MachineState.OFF.value
    led_supported: bool | None = None
    rumble_supported: bool | None = None
    error: str = ""


class PygameJoystickAdapter:
    def __init__(self, config, *, poll_period=0.01):
        self.config = config
        self.poll_period = float(poll_period)
        self._lock = threading.Lock()
        self._snapshot = InputSnapshot()
        self._selection_error = ""
        self._output_intent = MachineOutputIntent(MachineState.OFF)
        self._output_status = OutputStatus()
        self._active_output_intent = None
        self._applied_led = None
        self._blink_on = True
        self._next_blink = 0.0
        self._rumble_mode = "off"
        self._alarm_deadline = 0.0
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pygame-joystick", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def snapshot(self):
        with self._lock:
            return self._snapshot

    def set_machine_output(self, intent):
        if not isinstance(intent, MachineOutputIntent):
            raise TypeError("intent must be MachineOutputIntent")
        with self._lock:
            self._output_intent = intent

    def output_status(self):
        with self._lock:
            return self._output_status

    def _run(self):
        configure_sdl_dualsense_output()
        try:
            import pygame
        except ImportError:
            self._store(InputSnapshot(error="pygame-ce is not installed"))
            return

        pygame.init()
        pygame.joystick.init()
        joystick = None
        try:
            while not self._stop.is_set():
                pygame.event.pump()
                if joystick is None or not joystick.get_init():
                    joystick = self._select_device(pygame)
                if joystick is None:
                    self._store(InputSnapshot(error=self._selection_error or "Configured gamepad was not found"))
                else:
                    self._store(self._read_snapshot(joystick))
                    self._apply_output(joystick, time.monotonic())
                self._stop.wait(self.poll_period)
        finally:
            if joystick is not None:
                self._clear_output(joystick)
                joystick.quit()
            pygame.joystick.quit()
            pygame.quit()

    def _select_device(self, pygame):
        self._selection_error = ""
        matches = []
        for index in range(pygame.joystick.get_count()):
            device = pygame.joystick.Joystick(index)
            device.init()
            name = str(device.get_name()).strip()
            guid = str(device.get_guid()).strip().lower()
            if name == self.config.device_name and guid == self.config.device_guid:
                matches.append(device)
            else:
                device.quit()
        if len(matches) != 1:
            for device in matches:
                device.quit()
            if len(matches) > 1:
                self._selection_error = "More than one configured gamepad matched"
            return None
        error = device_profile_error(self.config, matches[0])
        if error:
            matches[0].quit()
            self._selection_error = error
            return None
        self._reset_output_device_state()
        return matches[0]

    def _read_snapshot(self, joystick):
        try:
            sticks = {
                name: float(joystick.get_axis(index))
                for name, index in self.config.stick_axes.items()
            }
            buttons = {
                name: bool(joystick.get_button(index))
                for name, index in self.config.buttons.items()
            }
            buttons["enable"] = self._read_enable_input(joystick)
            if self.config.hat is not None:
                hat = tuple(int(value) for value in joystick.get_hat(self.config.hat))
            else:
                dpad = {
                    name: bool(joystick.get_button(index))
                    for name, index in self.config.dpad_buttons.items()
                }
                hat = (
                    int(dpad["right"]) - int(dpad["left"]),
                    int(dpad["up"]) - int(dpad["down"]),
                )
            buttons.update(
                {
                    "dpad_up": hat[1] > 0,
                    "dpad_down": hat[1] < 0,
                    "dpad_left": hat[0] < 0,
                    "dpad_right": hat[0] > 0,
                }
            )
        except Exception as exc:
            return InputSnapshot(error=f"Gamepad input failed: {exc}")
        return InputSnapshot(
            sticks=sticks,
            buttons=buttons,
            hat=hat,
            connected=True,
            name=str(joystick.get_name()),
            guid=str(joystick.get_guid()).lower(),
        )

    def _read_enable_input(self, joystick):
        mapping = self.config.enable_input
        if mapping.source == "button":
            return bool(joystick.get_button(mapping.index))
        value = float(joystick.get_axis(mapping.index))
        if mapping.pressed_when == "above":
            return value >= mapping.threshold
        return value <= mapping.threshold

    def _store(self, snapshot):
        with self._lock:
            self._snapshot = snapshot

    def _apply_output(self, joystick, now):
        with self._lock:
            intent = self._output_intent
        state_changed = intent.state != getattr(self._active_output_intent, "state", None)
        if state_changed:
            self._active_output_intent = intent
            self._blink_on = True
            self._next_blink = 0.0
            self._applied_led = None
            if intent.state == MachineState.FAULT_ALARM:
                self._alarm_deadline = now + self.config.haptics.alarm.duration_ms / 1000.0
            else:
                self._alarm_deadline = 0.0
        else:
            self._active_output_intent = intent

        error = ""
        led_supported = self._output_status.led_supported
        rumble_supported = self._output_status.rumble_supported
        try:
            led_supported = self._apply_led(joystick, intent.state, now)
        except (OSError, RuntimeError) as exc:
            error = f"Lightbar output failed: {exc}"
        try:
            rumble_supported = self._apply_rumble(joystick, intent, now)
        except (OSError, RuntimeError) as exc:
            rumble_error = f"Rumble output failed: {exc}"
            error = f"{error}; {rumble_error}" if error else rumble_error
        with self._lock:
            self._output_status = OutputStatus(
                state=intent.state.value,
                led_supported=led_supported,
                rumble_supported=rumble_supported,
                error=error,
            )

    def _apply_led(self, joystick, state, now):
        state_config = self.config.lightbar.states[state.value]
        period = state_config.blink_period_ms / 1000.0
        if period > 0.0:
            half_period = period / 2.0
            if self._next_blink <= 0.0:
                self._next_blink = now + half_period
            while now >= self._next_blink:
                self._blink_on = not self._blink_on
                self._next_blink += half_period
        else:
            self._blink_on = True
            self._next_blink = 0.0
        color = (
            scaled_color(state_config.color, self.config.lightbar.brightness)
            if self.config.lightbar.enabled and self._blink_on
            else (0, 0, 0)
        )
        if color == self._applied_led:
            return self._output_status.led_supported
        supported = bool(joystick.set_led(color))
        self._applied_led = color
        return supported

    def _apply_rumble(self, joystick, intent, now):
        if not self.config.haptics.enabled:
            desired = "off"
        elif self._alarm_deadline > now:
            desired = "alarm"
        elif intent.motion_active:
            desired = "motion"
        else:
            desired = "off"
        if desired == self._rumble_mode:
            return self._output_status.rumble_supported
        if desired == "off":
            joystick.stop_rumble()
            supported = self._output_status.rumble_supported
        else:
            effect = (
                self.config.haptics.alarm
                if desired == "alarm"
                else self.config.haptics.motion
            )
            supported = bool(
                joystick.rumble(
                    effect.low_frequency,
                    effect.high_frequency,
                    effect.duration_ms,
                )
            )
        self._rumble_mode = desired
        return supported

    def _clear_output(self, joystick):
        try:
            joystick.stop_rumble()
        except (OSError, RuntimeError):
            pass
        try:
            joystick.set_led((0, 0, 0))
        except (OSError, RuntimeError):
            pass
        self._rumble_mode = "off"
        self._applied_led = (0, 0, 0)

    def _reset_output_device_state(self):
        self._active_output_intent = None
        self._applied_led = None
        self._blink_on = True
        self._next_blink = 0.0
        self._rumble_mode = "off"
        self._alarm_deadline = 0.0
        with self._lock:
            self._output_status = OutputStatus(state=self._output_intent.state.value)


def scaled_color(color, brightness):
    return tuple(max(0, min(255, round(channel * brightness))) for channel in color)


def device_profile_error(config, joystick):
    """Return the first profile index that the selected device cannot provide."""
    inputs = (
        ("stick axis", config.stick_axes, joystick.get_numaxes()),
        ("trigger axis", config.trigger_axes, joystick.get_numaxes()),
        ("button", config.buttons, joystick.get_numbuttons()),
    )
    if config.dpad_buttons is not None:
        inputs += (("D-pad button", config.dpad_buttons, joystick.get_numbuttons()),)
    for source, mapping, count in inputs:
        for name, index in mapping.items():
            if index >= count:
                return f"Device profile {source} {name} index {index} exceeds device count {count}"
    if config.hat is not None and config.hat >= joystick.get_numhats():
        return f"Device profile hat index {config.hat} exceeds device count {joystick.get_numhats()}"
    return ""


def list_pygame_devices():
    configure_sdl_dualsense_output()
    import pygame

    pygame.init()
    pygame.joystick.init()
    try:
        devices = []
        for index in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            devices.append(
                {
                    "index": index,
                    "name": str(joystick.get_name()),
                    "guid": str(joystick.get_guid()).lower(),
                    "axes": joystick.get_numaxes(),
                    "buttons": joystick.get_numbuttons(),
                    "hats": joystick.get_numhats(),
                }
            )
            joystick.quit()
        return devices
    finally:
        pygame.joystick.quit()
        pygame.quit()


def configure_sdl_dualsense_output():
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", "1")
