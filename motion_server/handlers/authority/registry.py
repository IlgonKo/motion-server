from motion_server.api.specification import authority_message_types
from motion_server.failure import AuthorityBusyException, AuthorityRequiredException
from motion_server.handlers.authority.status import authority_status_payload
from motion_server.app.authority_release import begin_authority_release


def log_authority(runtime, message):
    logger = getattr(runtime, "logger", None)
    if logger is not None:
        logger.status(message)


def acquire_authority(client, state, runtime):
    owner = state.get("command_authority_owner")
    if owner is None or owner == client["id"]:
        state["command_authority_owner"] = client["id"]
        payload = authority_status_payload(client, state, "system/authority/request")
        payload["granted"] = True
        payload["message"] = (
            "Command authority granted."
            if owner is None
            else "This connection already owns command authority."
        )
        log_authority(runtime, f"Command authority granted to client {client['id']}")
        return _authority_data(payload)

    log_authority(
        runtime,
        f"Command authority denied to client {client['id']}; owner={owner}",
    )
    raise AuthorityBusyException(owner)


def release_authority(client, state, runtime, message=None):
    request = message or {"cmd": "system/authority/release"}
    return begin_authority_release(request, client, state, runtime)


AUTHORITY_HANDLERS = {
    "system/authority/request": acquire_authority,
    "system/authority/release": release_authority,
    "system/authority/status": (
        lambda client, state, runtime: _authority_data(
            authority_status_payload(client, state)
        )
    ),
}


def validate_authority_registry():
    handler_names = set(AUTHORITY_HANDLERS)
    expected_names = authority_message_types()
    missing = sorted(expected_names - handler_names)
    unknown = sorted(handler_names - expected_names)
    if missing or unknown:
        raise RuntimeError(
            "Motion Server authority registry/specification mismatch. "
            f"missing={missing} unknown={unknown}"
        )


validate_authority_registry()


def handle_authority(message_type, message, client, state, runtime):
    handler = AUTHORITY_HANDLERS.get(message_type)
    if handler is None:
        from motion_server.failure import UnknownCommandException
        raise UnknownCommandException(message_type)
    if message_type == "system/authority/release":
        return handler(client, state, runtime, message)
    return handler(client, state, runtime)


def _authority_data(payload):
    data = dict(payload)
    data.pop("type", None)
    data.pop("ok", None)
    if data.get("reason") is None:
        data.pop("reason", None)
    return data
