import json
import select
import time
from collections.abc import Mapping

from motion_server.api.encoder import (
    ResponseContext,
    fail_response,
    send_client_message,
)
from motion_server.failure import InvalidRequestException, map_exception
from motion_server.handlers.status import system_feedback_message
from motion_server.app.authority_release import abort_owner_connection

HEARTBEAT_PERIOD_SECONDS = 0.05
HEARTBEAT_TIMEOUT_SECONDS = 0.2
UINT32_MODULUS = 1 << 32


def initialize_client_heartbeat(client, *, now=None):
    current_time = time.monotonic() if now is None else float(now)
    client["heartbeat_sequence"] = 0
    client["heartbeat_outstanding"] = False
    client["heartbeat_deadline"] = None
    client["next_heartbeat_time"] = current_time


def send_heartbeat_if_due(
    client,
    period=HEARTBEAT_PERIOD_SECONDS,
    timeout=HEARTBEAT_TIMEOUT_SECONDS,
    *,
    now=None,
):
    current_time = time.monotonic() if now is None else float(now)
    if client.get("heartbeat_outstanding", False):
        return False
    if current_time < client.get("next_heartbeat_time", current_time):
        return False
    send_client_message(
        client,
        {
            "type": "system/heartbeat",
            "sequence": int(client.get("heartbeat_sequence", 0)),
        },
    )
    client["heartbeat_outstanding"] = True
    client["heartbeat_period"] = float(period)
    client["heartbeat_deadline"] = current_time + float(timeout)
    client["next_heartbeat_time"] = current_time + float(period)
    return True


def heartbeat_timed_out(client, *, now=None):
    if not client.get("heartbeat_outstanding", False):
        return False
    current_time = time.monotonic() if now is None else float(now)
    return current_time >= float(client["heartbeat_deadline"])


def handle_heartbeat_ack(client, message, *, now=None):
    if message.get("type") != "system/heartbeat/ack":
        return False
    sequence = message.get("sequence")
    expected = (int(client.get("heartbeat_sequence", 0)) + 1) % UINT32_MODULUS
    if (
        client.get("heartbeat_outstanding", False)
        and set(message) == {"type", "sequence"}
        and isinstance(sequence, int)
        and not isinstance(sequence, bool)
        and 0 <= sequence < UINT32_MODULUS
        and sequence == expected
    ):
        current_time = time.monotonic() if now is None else float(now)
        client["heartbeat_sequence"] = sequence
        client["heartbeat_outstanding"] = False
        client["heartbeat_deadline"] = None
        client["next_heartbeat_time"] = current_time + float(
            client.get("heartbeat_period", HEARTBEAT_PERIOD_SECONDS)
        )
    return True


def service_client(client, runtime, state, dispatch_message):
    conn = client["conn"]
    readable, _, _ = select.select([conn], [], [], 0.0)
    if not readable:
        return True

    try:
        chunk = conn.recv(4096)
    except BlockingIOError:
        return True
    if not chunk:
        return False

    client["buffer"] += chunk.decode("utf-8")
    while "\n" in client["buffer"]:
        line, client["buffer"] = client["buffer"].split("\n", 1)
        if line.strip():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                _send_invalid_request(client, "malformed_json")
                continue
            if not isinstance(message, Mapping):
                _send_invalid_request(client, "request must be a JSON object")
                continue
            if handle_heartbeat_ack(client, message):
                continue
            dispatch_message(message, runtime, state, client)

    return True


def _send_invalid_request(client, reason):
    send_client_message(
        client,
        fail_response(
            ResponseContext("invalid_request"),
            map_exception(InvalidRequestException(reason)),
        ),
    )


def flush_client_output(client):
    output_buffer = client.get("output_buffer")
    if not output_buffer:
        return

    try:
        sent = client["conn"].send(output_buffer)
    except BlockingIOError:
        return

    if sent == 0:
        raise ConnectionError("client connection closed while sending")
    del output_buffer[:sent]


def send_feedback_if_due(client, runtime, state, feedback_period):
    now = time.monotonic()
    if now - client["last_feedback_time"] < feedback_period:
        return

    send_client_message(
        client,
        system_feedback_message(runtime, state, client["id"]),
    )
    client["last_feedback_time"] = now


def close_client(client, runtime, state):
    client_id = client["id"]
    if state.get("command_authority_owner") == client_id:
        if runtime is None:
            state["authority_release"] = None
            state["command_authority_owner"] = None
        else:
            abort_owner_connection(runtime, state, client_id)
        logger = getattr(runtime, "logger", None)
        if logger is not None:
            logger.status(
                "Command authority released after owner disconnect Quick Stop: "
                f"client={client_id}",
            )
    try:
        client["conn"].close()
    except OSError:
        pass
    logger = getattr(runtime, "logger", None)
    if logger is not None:
        logger.status(f"Client disconnected: id={client_id}")


def allocate_client_id(clients):
    next_id = 1
    used_ids = {client["id"] for client in clients}
    while next_id in used_ids:
        next_id += 1
    return next_id
