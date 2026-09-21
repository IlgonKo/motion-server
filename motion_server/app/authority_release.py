import time

from motion_server.api.deferred import DeferredResponse
from motion_server.api.encoder import (
    ResponseContext,
    fail_response,
    partial_fail_response,
    send_client_message,
    success_response,
)
from motion_server.app.state import inactive_trajectory_state
from motion_server.diagnostic import (
    AUTHORITY_RELEASE_FALLBACK,
    AUTHORITY_SHUTDOWN_FAILED,
    DiagnosticSource,
    DiagnosticSourceType,
)
from motion_server.failure import (
    AuthorityBusyException,
    AuthorityRequiredException,
    MotionServerException,
    PartialFailure,
    map_exception,
)
from motion_server.handlers.command.axis_state import (
    disable_motion_axes,
    stop_motion_axes,
)
from motion_server.handlers.command.homing import finish_homing


AUTHORITY_RELEASE_TIMEOUT_SECONDS = 2.0
MOVING_STATUSWORD_BIT = 1 << 8
SERVER_SOURCE = DiagnosticSource(DiagnosticSourceType.SERVER, 0)


def release_payload(*, mode="controlled_stop", fallback_reason=None):
    payload = {
        "granted": False,
        "owner": None,
        "owned_by_this_client": False,
        "available": True,
        "message": "Command authority released.",
        "release_mode": mode,
    }
    if fallback_reason is not None:
        payload["fallback_reason"] = fallback_reason
        payload["message"] = (
            "Command authority released after Disable/Quick Stop fallback."
        )
    return payload


def begin_authority_release(message, client, state, runtime):
    owner = state.get("command_authority_owner")
    if owner != client["id"]:
        if owner is None:
            raise AuthorityRequiredException()
        raise AuthorityBusyException(owner)

    if runtime is None or not getattr(runtime, "slaves", None):
        state["command_authority_owner"] = None
        state["authority_release"] = None
        return release_payload()

    state["authority_release"] = None
    reason = None
    try:
        _prepare_motion_shutdown(runtime, state, "authority_release")
        stop_result = stop_motion_axes(
            runtime,
            state,
            list(range(len(runtime.slaves))),
        )
        if isinstance(stop_result, PartialFailure):
            reason = "stop_failed"
    except (
        MotionServerException,
        OSError,
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ):
        reason = "stop_failed"

    if reason is not None:
        return _complete_with_fallback(state, runtime, reason)

    started_at = time.monotonic()
    state["authority_release"] = {
        "phase": "releasing",
        "owner": owner,
        "client": client,
        "context": ResponseContext.from_request(message),
        "started_at": started_at,
        "deadline": started_at + AUTHORITY_RELEASE_TIMEOUT_SECONDS,
    }
    return DeferredResponse()


def process_pending_authority_release(runtime, state, *, now=None):
    pending = state.get("authority_release")
    if not pending or pending.get("phase") != "releasing":
        return False

    if state.get("command_authority_owner") != pending["owner"]:
        state["authority_release"] = None
        return False

    if all_axes_standstill(runtime):
        state["command_authority_owner"] = None
        state["authority_release"] = None
        response = success_response(pending["context"], release_payload())
        send_client_message(pending["client"], response)
        _log(runtime, f"Command authority released by client {pending['owner']}")
        return True

    current_time = time.monotonic() if now is None else float(now)
    if current_time < pending["deadline"]:
        return False

    response = _fallback_response(
        state,
        runtime,
        pending["context"],
        "standstill_timeout",
    )
    send_client_message(pending["client"], response)
    return True


def abort_owner_connection(runtime, state, owner):
    if state.get("command_authority_owner") != owner:
        return None

    state["authority_release"] = None
    result = None
    preparation_failure = None
    try:
        _prepare_motion_shutdown(runtime, state, "owner_disconnect")
    except (
        MotionServerException,
        OSError,
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        preparation_failure = exc
        _record_shutdown_failure(state, "owner_disconnect_prepare", exc)
    try:
        result = disable_motion_axes(
            runtime,
            state,
            list(range(len(runtime.slaves))),
        )
        if isinstance(result, PartialFailure):
            _record_shutdown_failure(state, "owner_disconnect", result)
    except (
        MotionServerException,
        OSError,
        AttributeError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        result = exc
        _record_shutdown_failure(state, "owner_disconnect", exc)
    finally:
        state["command_authority_owner"] = None
    return preparation_failure or result


def all_axes_standstill(runtime):
    return all(
        not (int(slave.txpdo.statusword) & MOVING_STATUSWORD_BIT)
        for slave in runtime.slaves
    )


def _prepare_motion_shutdown(runtime, state, reason):
    if state.get("homing", {}).get("active"):
        finish_homing(runtime, state, "stopped", f"Homing stopped by {reason}.")
    state["trajectory"] = inactive_trajectory_state(reason)


def _complete_with_fallback(state, runtime, reason):
    try:
        result = _apply_fallback(state, runtime, reason)
    except MotionServerException:
        state["authority_release"] = {"phase": "failed", "reason": reason}
        raise
    if isinstance(result, PartialFailure):
        state["authority_release"] = {"phase": "failed", "reason": reason}
        return result
    state["command_authority_owner"] = None
    state["authority_release"] = None
    return release_payload(mode="quick_stop_fallback", fallback_reason=reason)


def _fallback_response(state, runtime, context, reason):
    try:
        result = _apply_fallback(state, runtime, reason)
    except MotionServerException as exc:
        state["authority_release"] = {"phase": "failed", "reason": reason}
        return fail_response(context, map_exception(exc))
    if isinstance(result, PartialFailure):
        state["authority_release"] = {"phase": "failed", "reason": reason}
        return partial_fail_response(context, result)

    state["command_authority_owner"] = None
    state["authority_release"] = None
    return success_response(
        context,
        release_payload(mode="quick_stop_fallback", fallback_reason=reason),
    )


def _apply_fallback(state, runtime, reason):
    try:
        result = disable_motion_axes(
            runtime,
            state,
            list(range(len(runtime.slaves))),
        )
    except MotionServerException as exc:
        _record_shutdown_failure(state, reason, exc)
        raise

    if isinstance(result, PartialFailure):
        _record_shutdown_failure(state, reason, result)
        return result

    state["diagnostic_manager"].detect(
        AUTHORITY_RELEASE_FALLBACK,
        SERVER_SOURCE,
        detail=reason,
        context={"reason": reason, "fallback": "disable_quick_stop"},
    )
    _log(runtime, f"Authority release used Quick Stop fallback: reason={reason}")
    return result


def _record_shutdown_failure(state, reason, failure):
    manager = state.get("diagnostic_manager")
    if manager is None:
        return
    manager.detect(
        AUTHORITY_SHUTDOWN_FAILED,
        SERVER_SOURCE,
        detail=reason,
        context={"reason": reason, "failure_type": type(failure).__name__},
    )


def _log(runtime, message):
    logger = getattr(runtime, "logger", None)
    if logger is not None:
        logger.status(message)
