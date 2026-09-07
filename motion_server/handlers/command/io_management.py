from device.capabilities import DeviceCapability
from motion_server.api.decoder import public_command_name
from motion_server.diagnostic.models import DiagnosticSource, DiagnosticSourceType
from motion_server.failure import (
    InvalidArgumentException,
    ResourceNotFoundException,
    UnsupportedOperationException,
)


def reset_io_device(message, runtime, state, client):
    return _run_io_capability(
        message,
        runtime,
        DeviceCapability.IO_RESET,
        "reset_io_device",
        "I/O reset completed.",
        state=state,
        acknowledge_faults=True,
    )


def restart_io_device(message, runtime, state, client):
    return _run_io_capability(
        message,
        runtime,
        DeviceCapability.IO_RESTART,
        "restart_io_device",
        "I/O restart completed.",
    )


PARAMETER_STORAGE_MODES = {
    "volatile": "volatile",
    "non_volatile": "non_volatile",
}


def set_io_parameter_storage(message, runtime, state, client):
    mode = _required_parameter_storage_mode(message)
    return _run_io_capability(
        message,
        runtime,
        DeviceCapability.IO_PARAMETER_STORAGE,
        "set_io_parameter_storage",
        "I/O parameter storage mode set.",
        mode,
    )


def _run_io_capability(
    message,
    runtime,
    capability,
    method_name,
    message_text,
    *method_args,
    state=None,
    acknowledge_faults=False,
):
    command = public_command_name(message)
    io_selector = _required_io_selector(message)
    device = _selected_io_device(runtime, io_selector)
    profile = _device_profile(device)
    if capability not in getattr(profile, "capabilities", frozenset()):
        raise UnsupportedOperationException(
            command,
            f"Device profile {profile.name!r} does not support {command}.",
        )
    method = getattr(profile, method_name)
    slave_index = int(device["slave_index"])
    result = method(_io_ethercat_master(runtime), slave_index, *method_args)
    data = {
        "io": device["id"],
        "slave_index": slave_index,
        "result": result,
        "message": message_text,
    }
    if acknowledge_faults:
        statuses = _acknowledge_io_faults(runtime, state, device)
        data["fault_count"] = len(statuses)
    return data


def _required_io_selector(message):
    if "io" not in message:
        raise InvalidArgumentException("io", "is required")
    return message.get("io")


def _required_parameter_storage_mode(message):
    raw_mode = str(message.get("mode", "")).strip().lower()
    if raw_mode not in PARAMETER_STORAGE_MODES:
        raise InvalidArgumentException(
            "mode",
            "must be one of: volatile, non_volatile",
            public_value=message.get("mode"),
        )
    return PARAMETER_STORAGE_MODES[raw_mode]


def _selected_io_device(runtime, io_selector):
    try:
        slave_index = runtime.device_manager.io.slave_index(io_selector)
        return runtime.device_manager.io.selected_device(slave_index=slave_index)
    except (TypeError, ValueError, AttributeError) as exception:
        raise ResourceNotFoundException("io", io_selector) from exception


def _device_profile(device):
    profile = getattr(device["slave"], "device_profile", None)
    if profile is None:
        raise UnsupportedOperationException(
            "io_management",
            "Selected I/O device does not expose a device profile.",
        )
    return profile


def _io_ethercat_master(runtime):
    io_group = getattr(getattr(runtime, "device_manager", None), "io", None)
    return getattr(io_group, "ethercat_master", runtime)


def _acknowledge_io_faults(runtime, state, device):
    manager = None
    if state is not None:
        manager = state.get("diagnostic_manager")
    if manager is None:
        manager = getattr(runtime, "diagnostic_manager", None)
    if manager is None:
        return ()
    source = DiagnosticSource(
        DiagnosticSourceType.IO,
        _io_source_index(runtime, device),
    )
    return manager.acknowledge_faults(source=source)


def _io_source_index(runtime, selected_device):
    selected_id = str(selected_device["id"])
    selected_slave_index = int(selected_device["slave_index"])
    for io_index, device in enumerate(runtime.device_manager.io.devices):
        if str(device["id"]) == selected_id:
            return io_index
        if int(device["slave_index"]) == selected_slave_index:
            return io_index
    return 0
