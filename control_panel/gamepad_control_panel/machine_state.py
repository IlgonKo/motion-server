from dataclasses import dataclass
from enum import Enum


MOVING_BIT = 1 << 8
FAULT_BIT = 1 << 3


class MachineState(str, Enum):
    OFF = "off"
    CONNECTED_DISARMED = "connected_disarmed"
    AUTHORITY_OWNED = "authority_owned"
    ARMED = "armed"
    MOVING = "moving"
    HOMING = "homing"
    WARNING = "warning"
    FAULT_ALARM = "fault_alarm"


MACHINE_STATE_NAMES = tuple(state.value for state in MachineState)


@dataclass(frozen=True)
class MachineOutputIntent:
    state: MachineState
    motion_active: bool = False


def resolve_machine_output(
    *,
    server_connected,
    controller_state,
    owns_authority,
    statuswords,
    active_axes,
    warning_active=False,
    alarm_active=False,
):
    words = list(statuswords or ())
    axes = tuple(int(axis) for axis in active_axes)
    motion_active = _any_axis_bit(words, axes, MOVING_BIT)
    fault_active = _any_axis_bit(words, axes, FAULT_BIT)

    if alarm_active or fault_active:
        state = MachineState.FAULT_ALARM
    elif warning_active:
        state = MachineState.WARNING
    elif controller_state == "Homing":
        state = MachineState.HOMING
    elif motion_active:
        state = MachineState.MOVING
    elif controller_state in {"Arming", "Armed"}:
        state = MachineState.ARMED
    elif owns_authority:
        state = MachineState.AUTHORITY_OWNED
    elif server_connected:
        state = MachineState.CONNECTED_DISARMED
    else:
        state = MachineState.OFF
    return MachineOutputIntent(state=state, motion_active=motion_active)


def _any_axis_bit(statuswords, axes, bit):
    return any(
        0 <= axis < len(statuswords) and bool(int(statuswords[axis]) & bit)
        for axis in axes
    )
