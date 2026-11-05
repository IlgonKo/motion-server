from dataclasses import dataclass
import json
import math
from pathlib import Path

from control_panel.gamepad_control_panel.machine_state import MACHINE_STATE_NAMES


ROLES = ("x", "y", "z", "rotation")
STICKS = ("left_x", "left_y", "right_x", "right_y")
BUTTONS = (
    "l1",
    "r1",
    "l3",
    "r3",
    "cross",
    "circle",
    "square",
    "triangle",
    "options",
    "create",
    "touchpad",
)
TRIGGERS = ("l2", "r2")
DIRECTIONS = ("up", "down", "left", "right")
ACTION_NAMES = (
    "enable",
    "authority_toggle",
    "fault_reset",
    "stop",
    "all_axes_stop",
    "mode_toggle",
    "homing",
    "speed_up",
    "speed_down",
    "previous_axis",
    "next_axis",
)

DEFAULT_HAPTICS = {
    "enabled": True,
    "motion": {"low_frequency": 0.05, "high_frequency": 0.10},
    "alarm": {
        "low_frequency": 0.80,
        "high_frequency": 1.00,
        "duration_ms": 2000,
    },
}
DEFAULT_LIGHTBAR = {
    "enabled": True,
    "brightness": 0.35,
    "states": {
        "connected_disarmed": {"color": "#0050FF", "blink_period_ms": 0},
        "authority_owned": {"color": "#00B4B4", "blink_period_ms": 0},
        "armed": {"color": "#00C828", "blink_period_ms": 0},
        "moving": {"color": "#0091DC", "blink_period_ms": 0},
        "homing": {"color": "#A03CFF", "blink_period_ms": 1000},
        "warning": {"color": "#FFB400", "blink_period_ms": 1000},
        "fault_alarm": {"color": "#FF0000", "blink_period_ms": 500},
        "off": {"color": "#000000", "blink_period_ms": 0},
    },
}


@dataclass(frozen=True)
class EnableInputConfig:
    control: str
    source: str
    index: int
    threshold: float | None = None
    pressed_when: str | None = None


@dataclass(frozen=True)
class HapticEffectConfig:
    low_frequency: float
    high_frequency: float
    duration_ms: int = 0


@dataclass(frozen=True)
class HapticsConfig:
    enabled: bool
    motion: HapticEffectConfig
    alarm: HapticEffectConfig


@dataclass(frozen=True)
class LightbarStateConfig:
    color: tuple[int, int, int]
    blink_period_ms: int


@dataclass(frozen=True)
class LightbarConfig:
    enabled: bool
    brightness: float
    states: dict[str, LightbarStateConfig]


@dataclass(frozen=True)
class GamepadConfig:
    host: str
    port: int
    request_timeout: float
    device_name: str
    device_guid: str
    device_profile: str
    server_axes: dict[str, int]
    axis_inputs: dict[str, str]
    invert: dict[str, bool]
    stick_axes: dict[str, int]
    trigger_axes: dict[str, int]
    buttons: dict[str, int]
    enable_input: EnableInputConfig
    actions: dict[str, str]
    hat: int | None
    dpad_buttons: dict[str, int] | None
    deadzone: float
    update_period: float
    speed_scales: tuple[float, ...]
    speed_scale_default: float
    haptics: HapticsConfig
    lightbar: LightbarConfig


def load_config(path, profiles_path=None):
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load gamepad config: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Gamepad config root must be an object")

    server = required_object(value, "server")
    device = required_object(value, "device")
    device_profile = required_text(device, "profile")
    mapping = load_device_mapping(source, device_profile, profiles_path)
    server_axis_values = required_object(server, "axes")
    if set(server_axis_values) != set(ROLES):
        raise ValueError(f"server.axes must contain exactly {list(ROLES)}")
    server_axes = {
        role: strict_int(server_axis_values[role], f"server.axes.{role}", minimum=0)
        for role in ROLES
        if server_axis_values[role] is not None
    }
    if not server_axes:
        raise ValueError("server.axes must configure at least one Axis")
    if len(set(server_axes.values())) != len(server_axes):
        raise ValueError("server.axes role indices must be unique")
    axis_inputs = text_map(required_object(value, "axes"), ROLES, "axes")
    if set(axis_inputs.values()) != set(STICKS):
        raise ValueError(f"axes values must use each logical stick input exactly once: {list(STICKS)}")
    invert = boolean_map(required_object(value, "invert"), ROLES, "invert")
    stick_axes = integer_map(required_object(mapping, "axes"), STICKS, "mapping.axes")
    trigger_axes = integer_map(
        required_object(mapping, "triggers"), TRIGGERS, "mapping.triggers"
    )
    buttons = integer_map(required_object(mapping, "buttons"), BUTTONS, "mapping.buttons")
    raw_hat = mapping.get("hat")
    raw_dpad_buttons = mapping.get("dpad_buttons")
    if raw_hat is None:
        if not isinstance(raw_dpad_buttons, dict):
            raise ValueError("mapping.dpad_buttons is required when mapping.hat is null")
        hat = None
        dpad_buttons = integer_map(raw_dpad_buttons, DIRECTIONS, "mapping.dpad_buttons")
    else:
        hat = strict_int(raw_hat, "mapping.hat", minimum=0)
        if raw_dpad_buttons is not None:
            raise ValueError("mapping.dpad_buttons must be null or omitted when mapping.hat is used")
        dpad_buttons = None
    enable_input, actions = parse_actions(
        required_object(value, "actions"), buttons, trigger_axes
    )
    deadzone = finite_number(value.get("deadzone"), "deadzone")
    if not 0.0 <= deadzone < 1.0:
        raise ValueError("deadzone must satisfy 0 <= value < 1")
    update_period_ms = finite_number(value.get("update_period_ms"), "update_period_ms")
    if update_period_ms <= 0.0:
        raise ValueError("update_period_ms must be > 0")
    raw_scales = value.get("speed_scales")
    if not isinstance(raw_scales, list) or not raw_scales:
        raise ValueError("speed_scales must be a non-empty array")
    scales = tuple(finite_number(item, "speed_scales") for item in raw_scales)
    if any(not 0.0 < item <= 1.0 for item in scales) or list(scales) != sorted(set(scales)):
        raise ValueError("speed_scales must be unique ascending values in (0, 1]")
    default_scale = finite_number(value.get("speed_scale_default"), "speed_scale_default")
    if default_scale not in scales:
        raise ValueError("speed_scale_default must be present in speed_scales")

    host = required_text(server, "host")
    port = strict_int(server.get("port"), "server.port", minimum=1, maximum=65535)
    request_timeout = finite_number(server.get("request_timeout", 3.0), "server.request_timeout")
    if request_timeout <= 0.0:
        raise ValueError("server.request_timeout must be > 0")

    return GamepadConfig(
        host=host,
        port=port,
        request_timeout=request_timeout,
        device_name=required_text(device, "name"),
        device_guid=required_text(device, "guid").lower(),
        device_profile=device_profile,
        server_axes=server_axes,
        axis_inputs=axis_inputs,
        invert=invert,
        stick_axes=stick_axes,
        trigger_axes=trigger_axes,
        buttons=buttons,
        enable_input=enable_input,
        actions=actions,
        hat=hat,
        dpad_buttons=dpad_buttons,
        deadzone=deadzone,
        update_period=update_period_ms / 1000.0,
        speed_scales=scales,
        speed_scale_default=default_scale,
        haptics=parse_haptics(value.get("haptics", DEFAULT_HAPTICS)),
        lightbar=parse_lightbar(value.get("lightbar", DEFAULT_LIGHTBAR)),
    )


def parse_haptics(value):
    if not isinstance(value, dict):
        raise ValueError("haptics must be an object")
    if set(value) != {"enabled", "motion", "alarm"}:
        raise ValueError("haptics must contain exactly enabled, motion, and alarm")
    if type(value["enabled"]) is not bool:
        raise ValueError("haptics.enabled must be Boolean")
    motion = parse_haptic_effect(value["motion"], "haptics.motion", timed=False)
    alarm = parse_haptic_effect(value["alarm"], "haptics.alarm", timed=True)
    return HapticsConfig(enabled=value["enabled"], motion=motion, alarm=alarm)


def parse_haptic_effect(value, field, *, timed):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    expected = {"low_frequency", "high_frequency"}
    if timed:
        expected.add("duration_ms")
    if set(value) != expected:
        raise ValueError(f"{field} must contain exactly {sorted(expected)}")
    low = finite_number(value["low_frequency"], f"{field}.low_frequency")
    high = finite_number(value["high_frequency"], f"{field}.high_frequency")
    if not 0.0 <= low <= 1.0 or not 0.0 <= high <= 1.0:
        raise ValueError(f"{field} frequency values must be in [0, 1]")
    duration = 0
    if timed:
        duration = strict_int(value["duration_ms"], f"{field}.duration_ms", minimum=1)
    return HapticEffectConfig(low_frequency=low, high_frequency=high, duration_ms=duration)


def parse_lightbar(value):
    if not isinstance(value, dict):
        raise ValueError("lightbar must be an object")
    if set(value) != {"enabled", "brightness", "states"}:
        raise ValueError("lightbar must contain exactly enabled, brightness, and states")
    if type(value["enabled"]) is not bool:
        raise ValueError("lightbar.enabled must be Boolean")
    brightness = finite_number(value["brightness"], "lightbar.brightness")
    if not 0.0 <= brightness <= 1.0:
        raise ValueError("lightbar.brightness must be in [0, 1]")
    raw_states = value["states"]
    if not isinstance(raw_states, dict) or set(raw_states) != set(MACHINE_STATE_NAMES):
        raise ValueError(f"lightbar.states must contain exactly {list(MACHINE_STATE_NAMES)}")
    states = {
        name: parse_lightbar_state(raw_states[name], f"lightbar.states.{name}")
        for name in MACHINE_STATE_NAMES
    }
    return LightbarConfig(enabled=value["enabled"], brightness=brightness, states=states)


def parse_lightbar_state(value, field):
    if not isinstance(value, dict) or set(value) != {"color", "blink_period_ms"}:
        raise ValueError(f"{field} must contain exactly color and blink_period_ms")
    color = value["color"]
    if not isinstance(color, str) or len(color) != 7 or color[0] != "#":
        raise ValueError(f"{field}.color must use #RRGGBB")
    try:
        rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError as exc:
        raise ValueError(f"{field}.color must use #RRGGBB") from exc
    period = strict_int(value["blink_period_ms"], f"{field}.blink_period_ms", minimum=0)
    return LightbarStateConfig(color=rgb, blink_period_ms=period)


def load_device_mapping(config_path, profile_name, profiles_path=None):
    if profiles_path is None:
        adjacent = config_path.parent / "device_profiles.json"
        profiles_path = adjacent if adjacent.exists() else Path(__file__).with_name(
            "device_profiles.json"
        )
    source = Path(profiles_path)
    try:
        catalog = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load gamepad device profiles: {exc}") from exc
    if not isinstance(catalog, dict):
        raise ValueError("Gamepad device profile catalog root must be an object")
    profiles = required_object(catalog, "profiles")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise ValueError(f"Unknown gamepad device profile: {profile_name}")
    return required_object(profile, "mapping")


def required_object(value, key):
    result = value.get(key)
    if not isinstance(result, dict):
        raise ValueError(f"{key} must be an object")
    return result


def required_text(value, key):
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return result.strip()


def strict_int(value, field, *, minimum=None, maximum=None):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return value


def finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def integer_map(value, keys, field):
    if set(value) != set(keys):
        raise ValueError(f"{field} must contain exactly {list(keys)}")
    return {key: strict_int(value[key], f"{field}.{key}", minimum=0) for key in keys}


def text_map(value, keys, field):
    if set(value) != set(keys):
        raise ValueError(f"{field} must contain exactly {list(keys)}")
    return {key: required_text(value, key) for key in keys}


def boolean_map(value, keys, field):
    if set(value) != set(keys) or any(type(value[key]) is not bool for key in keys):
        raise ValueError(f"{field} must contain exactly Boolean values for {list(keys)}")
    return dict(value)


def parse_enable_input(value, buttons, trigger_axes):
    control = required_text(value, "control").lower()
    if control in buttons:
        if set(value) != {"control"}:
            raise ValueError("button actions.enable must contain exactly control")
        return EnableInputConfig(
            control=control,
            source="button",
            index=buttons[control],
        )
    if control not in trigger_axes:
        raise ValueError("actions.enable.control must name a configured button or trigger")
    if set(value) != {"control", "threshold", "pressed_when"}:
        raise ValueError(
            "trigger actions.enable must contain exactly control, threshold, and pressed_when"
        )
    threshold = finite_number(value.get("threshold"), "actions.enable.threshold")
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("actions.enable.threshold must be in [-1, 1]")
    pressed_when = required_text(value, "pressed_when").lower()
    if pressed_when not in {"above", "below"}:
        raise ValueError("actions.enable.pressed_when must be above or below")
    return EnableInputConfig(
        control=control,
        source="axis",
        index=trigger_axes[control],
        threshold=threshold,
        pressed_when=pressed_when,
    )


def parse_actions(value, buttons, trigger_axes):
    if set(value) != set(ACTION_NAMES):
        raise ValueError(f"actions must contain exactly {list(ACTION_NAMES)}")
    enable_value = value.get("enable")
    if not isinstance(enable_value, dict):
        raise ValueError("actions.enable must be an object")
    enable_input = parse_enable_input(enable_value, buttons, trigger_axes)
    actions = {
        name: required_text(value, name).lower()
        for name in ACTION_NAMES
        if name != "enable"
    }
    available = set(buttons) | {f"dpad_{direction}" for direction in DIRECTIONS}
    unknown = sorted(set(actions.values()) - available)
    if unknown:
        raise ValueError(f"actions reference unknown digital controls: {unknown}")
    if len(set(actions.values())) != len(actions):
        raise ValueError("actions must use unique digital controls")
    if enable_input.control in actions.values():
        raise ValueError("actions must not reuse actions.enable.control")
    return enable_input, actions
