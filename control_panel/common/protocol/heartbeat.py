HEARTBEAT_TIMEOUT_SECONDS = 0.2
HEARTBEAT_POLL_SECONDS = 0.05
UINT32_MODULUS = 1 << 32


def heartbeat_ack(message):
    if message.get("type") != "system/heartbeat":
        return None
    sequence = message.get("sequence")
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 0 <= sequence < UINT32_MODULUS
    ):
        raise ValueError("Invalid Motion Server Heartbeat sequence")
    return {
        "type": "system/heartbeat/ack",
        "sequence": (sequence + 1) % UINT32_MODULUS,
    }
