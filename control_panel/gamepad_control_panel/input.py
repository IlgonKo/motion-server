from dataclasses import dataclass, field
import threading
import time


@dataclass(frozen=True)
class InputSnapshot:
    sticks: dict[str, float] = field(default_factory=dict)
    buttons: dict[str, bool] = field(default_factory=dict)
    hat: tuple[int, int] = (0, 0)
    connected: bool = False
    name: str = ""
    guid: str = ""
    error: str = ""


class PygameJoystickAdapter:
    def __init__(self, config, *, poll_period=0.01):
        self.config = config
        self.poll_period = float(poll_period)
        self._lock = threading.Lock()
        self._snapshot = InputSnapshot()
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

    def _run(self):
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
                    self._store(InputSnapshot(error="Configured gamepad was not found"))
                else:
                    self._store(self._read_snapshot(joystick))
                self._stop.wait(self.poll_period)
        finally:
            if joystick is not None:
                joystick.quit()
            pygame.joystick.quit()
            pygame.quit()

    def _select_device(self, pygame):
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
                self._store(InputSnapshot(error="More than one configured gamepad matched"))
            return None
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


def list_pygame_devices():
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
