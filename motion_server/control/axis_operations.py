from motion_server.control.pdo_contract import require_pdo_fields_for_mode
from motion_server.device_manager.profile_access import axis_device_profile
from motion_server.app.cycle import exchange
from motion_server.api import raise_operation_rejected


def axis_count(runtime):
    return len(runtime.slaves)


def faulted_axes(runtime):
    return [
        axis_index
        for axis_index, slave in enumerate(runtime.slaves)
        if int(slave.txpdo.statusword) & 0x0008
    ]


def actual_positions(runtime):
    return [
        float(slave.txpdo.actual_position)
        for slave in runtime.slaves
    ]


def hold_axis_at_actual_position(runtime, state, axis_index):
    state["target_positions"] = runtime.hold_axes(
        state["target_positions"],
        [axis_index],
    )


def hold_faulted_axes(runtime, state):
    axes = set(faulted_axes(runtime))
    handled = state.setdefault("handled_drive_fault_axes", set())
    handled.intersection_update(axes)
    for axis_index in sorted(axes - handled):
        _cancel_faulted_axis(runtime, state, axis_index)
        handled.add(axis_index)


def _cancel_faulted_axis(runtime, state, axis_index):
    slave = runtime.slaves[axis_index]
    # Remove motion/start/reset bits and Enable Operation before changing mode.
    slave.rxpdo.controlword = 0x0007
    hold_axis_at_actual_position(runtime, state, axis_index)
    runtime.sync_velocity_command(axis_index, 0.0)
    for field in ("target_velocity", "velocity_offset"):
        if slave.rxpdo.has_field(field):
            setattr(slave.rxpdo, field, 0)

    mode = state["motion_modes"][axis_index]
    homing = state.get("homing", {})
    if mode == "homing":
        mode = homing.get("original_motion_modes", {}).get(axis_index, mode)
    # Homing may itself have been entered from Jog.
    if mode == "jog":
        mode = state["jog_previous_modes"][axis_index] or mode
    slave.rxpdo.mode_of_operation = axis_device_profile(runtime, axis_index).mode_code(mode)
    state["motion_modes"][axis_index] = mode
    state["jog_previous_modes"][axis_index] = None
    update_motion_mode_summary(state)

    # Cancel only this axis; peer axes are left to the owning controller.
    for operation in (homing, state.get("trajectory", {})):
        if operation.get("active") and axis_index in operation.get("axes", []):
            cancelled = operation.setdefault("fault_cancelled_axes", [])
            if axis_index not in cancelled:
                cancelled.append(axis_index)
            if set(operation["axes"]).issubset(cancelled):
                operation["active"] = False
                operation["state"] = "fault"
                operation["message"] = "Drive Fault cancelled axis motion."


def operation_enabled_axes(runtime, axes):
    return [
        axis_index
        for axis_index in axes
        if int(runtime.slaves[axis_index].txpdo.statusword) & 0x0004
    ]


def disabled_operation_axes(runtime, axes):
    enabled = set(operation_enabled_axes(runtime, axes))
    return [
        axis_index
        for axis_index in axes
        if axis_index not in enabled
    ]


def reject_if_any_axis_disabled(runtime, axes, client, command):
    disabled_axes = disabled_operation_axes(runtime, axes)
    if not disabled_axes:
        return False

    raise_operation_rejected(client, command, "Axis operation is disabled.")


def pv_allowed_axis(state, axis_index):
    return state["axis_devices"].pv_allowed(axis_index)


def pv_reject_message(state, axis_indices):
    details = []
    for axis_index in axis_indices:
        units = state["axis_devices"].user_position_units
        user_position_unit = units[axis_index] if axis_index < len(units) else None
        if user_position_unit is None:
            details.append(f"axis {axis_index}: 0x216E:01 unread")
        else:
            details.append(
                f"axis {axis_index}: 0x216E:01=0x{int(user_position_unit):04X} "
                f"unit={state['axis_devices'].user_position_unit_name(user_position_unit)}"
            )
    return (
        "PV mode requires a known linear or rotary user position unit. "
        + "; ".join(details)
    )


def reject_if_pv_not_allowed(state, axis_indices, client, command):
    blocked_axes = [
        axis_index
        for axis_index in axis_indices
        if not pv_allowed_axis(state, axis_index)
    ]
    if not blocked_axes:
        return False

    message = pv_reject_message(state, blocked_axes)
    raise_operation_rejected(client, command, message)


def mode_code(runtime, mode_name, axis_index=0):
    return axis_device_profile(runtime, axis_index).mode_code(mode_name)


def configure_motion_mode(runtime, mode_name, axis_index=None):
    require_pdo_fields_for_mode(runtime, mode_name, axis_index)
    configure_mode_code(runtime, mode_name, axis_index)


def configure_mode_code(runtime, mode_name, axis_index=None):
    axis_indices = (
        range(axis_count(runtime))
        if axis_index is None
        else [axis_index]
    )
    for current_axis in axis_indices:
        profile = axis_device_profile(runtime, current_axis)
        code = profile.mode_code(mode_name)
        runtime.slaves[current_axis].rxpdo.mode_of_operation = code
        profile.configure_mode_code(runtime, current_axis, code)
    exchange(runtime, cycles=5)


def update_motion_mode_summary(state):
    modes = state["motion_modes"]
    state["motion_mode"] = modes[0] if len(set(modes)) == 1 else "mixed"


def ensure_csp_mode(runtime, state, axis_indices):
    changed = False
    for axis_index in axis_indices:
        if state["motion_modes"][axis_index] != "csp":
            hold_axis_at_actual_position(runtime, state, axis_index)
            profile = axis_device_profile(runtime, axis_index)
            runtime.slaves[axis_index].rxpdo.mode_of_operation = profile.CSP_MODE
            runtime.slaves[axis_index].rxpdo.controlword = 0x000F
            state["motion_modes"][axis_index] = "csp"
            changed = True

    if changed:
        update_motion_mode_summary(state)
        runtime.set_target_positions(state["target_positions"])
