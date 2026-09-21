import unittest
import json
from unittest.mock import patch

from motion_server.api.encoder import (
    MAX_CLIENT_OUTPUT_BUFFER_BYTES,
    send_client_message,
)
from motion_server.app.client_transport import (
    flush_client_output,
    handle_heartbeat_ack,
    heartbeat_timed_out,
    initialize_client_heartbeat,
    send_heartbeat_if_due,
    service_client,
)


class _ReceiveWouldBlockSocket:
    def recv(self, _size):
        raise BlockingIOError(10035, "operation would block")


class _BufferedSendSocket:
    def __init__(self):
        self.calls = 0
        self.sent = bytearray()

    def send(self, payload):
        self.calls += 1
        if self.calls == 1:
            raise BlockingIOError(10035, "operation would block")
        count = min(3, len(payload))
        self.sent.extend(payload[:count])
        return count


class _LineSocket:
    def __init__(self, payload):
        self.payload = payload

    def recv(self, _size):
        payload = self.payload
        self.payload = b""
        return payload


class ClientTransportTests(unittest.TestCase):
    def test_heartbeat_challenge_ack_and_next_sequence(self):
        client = {"conn": _BufferedSendSocket(), "output_buffer": bytearray()}
        initialize_client_heartbeat(client, now=10.0)

        self.assertTrue(send_heartbeat_if_due(client, now=10.0))
        challenge = json.loads(bytes(client["output_buffer"]).splitlines()[0])
        self.assertEqual(challenge, {"type": "system/heartbeat", "sequence": 0})
        self.assertTrue(
            handle_heartbeat_ack(
                client,
                {"type": "system/heartbeat/ack", "sequence": 1},
                now=10.01,
            )
        )
        self.assertFalse(client["heartbeat_outstanding"])
        self.assertEqual(client["heartbeat_sequence"], 1)

    def test_invalid_heartbeat_ack_does_not_extend_deadline(self):
        client = {"conn": _BufferedSendSocket(), "output_buffer": bytearray()}
        initialize_client_heartbeat(client, now=1.0)
        send_heartbeat_if_due(client, timeout=0.2, now=1.0)

        deadline = client["heartbeat_deadline"]
        handle_heartbeat_ack(
            client,
            {"type": "system/heartbeat/ack", "sequence": 99},
            now=1.1,
        )

        self.assertEqual(client["heartbeat_deadline"], deadline)
        self.assertTrue(heartbeat_timed_out(client, now=1.2))

    def test_heartbeat_uint32_wraps_to_zero(self):
        client = {"conn": _BufferedSendSocket(), "output_buffer": bytearray()}
        initialize_client_heartbeat(client, now=1.0)
        client["heartbeat_sequence"] = (1 << 32) - 1
        send_heartbeat_if_due(client, now=1.0)

        handle_heartbeat_ack(
            client,
            {"type": "system/heartbeat/ack", "sequence": 0},
            now=1.01,
        )

        self.assertEqual(client["heartbeat_sequence"], 0)
        self.assertFalse(client["heartbeat_outstanding"])

    @patch("motion_server.app.client_transport.select.select")
    def test_heartbeat_ack_is_not_dispatched_or_answered(self, select_mock):
        connection = _LineSocket(
            b'{"type":"system/heartbeat/ack","sequence":1}\n'
        )
        select_mock.return_value = ([connection], [], [])
        client = {
            "conn": connection,
            "buffer": "",
            "output_buffer": bytearray(),
        }
        initialize_client_heartbeat(client, now=1.0)
        client["heartbeat_outstanding"] = True
        dispatched = []

        self.assertTrue(
            service_client(
                client,
                None,
                {},
                lambda message, *_: dispatched.append(message),
            )
        )

        self.assertEqual(dispatched, [])
        self.assertEqual(client["output_buffer"], bytearray())

    @patch("motion_server.app.client_transport.select.select")
    def test_receive_would_block_keeps_client_connected(self, select_mock):
        connection = _ReceiveWouldBlockSocket()
        select_mock.return_value = ([connection], [], [])
        client = {"conn": connection, "buffer": ""}

        self.assertTrue(service_client(client, None, {}, lambda *_: None))

    def test_output_is_retained_across_would_block_and_partial_send(self):
        connection = _BufferedSendSocket()
        client = {"conn": connection, "output_buffer": bytearray()}
        send_client_message(client, {"result": "success"})
        expected = bytes(client["output_buffer"])

        flush_client_output(client)
        self.assertEqual(bytes(client["output_buffer"]), expected)

        while client["output_buffer"]:
            flush_client_output(client)

        self.assertEqual(bytes(connection.sent), expected)

    def test_output_buffer_accepts_catalog_sized_message(self):
        client = {"conn": _BufferedSendSocket(), "output_buffer": bytearray()}

        send_client_message(client, {"objects": "x" * (2 * 1024 * 1024)})

        self.assertGreater(len(client["output_buffer"]), 2 * 1024 * 1024)
        self.assertLessEqual(
            len(client["output_buffer"]),
            MAX_CLIENT_OUTPUT_BUFFER_BYTES,
        )

    def test_output_buffer_rejects_accumulation_above_limit(self):
        client = {
            "conn": _BufferedSendSocket(),
            "output_buffer": bytearray(MAX_CLIENT_OUTPUT_BUFFER_BYTES),
        }

        with self.assertRaisesRegex(ConnectionError, "output buffer limit"):
            send_client_message(client, {"result": "success"})

    @patch("motion_server.app.client_transport.select.select")
    def test_malformed_json_is_failed_without_closing_client(self, select_mock):
        connection = _LineSocket(
            b"{bad json}\n{\"cmd\":\"system/server/status\"}\n"
        )
        select_mock.return_value = ([connection], [], [])
        client = {
            "conn": connection,
            "buffer": "",
            "output_buffer": bytearray(),
        }
        dispatched = []

        result = service_client(
            client,
            None,
            {},
            lambda message, *_: dispatched.append(message),
        )

        self.assertTrue(result)
        self.assertEqual(dispatched, [{"cmd": "system/server/status"}])
        response = json.loads(bytes(client["output_buffer"]).splitlines()[0])
        self.assertEqual(response["type"], "invalid_request")
        self.assertEqual(response["result"], "fail")
        self.assertEqual(response["failure"]["code"], "INVALID_REQUEST")

    @patch("motion_server.app.client_transport.select.select")
    def test_non_object_json_is_failed_without_dispatch(self, select_mock):
        connection = _LineSocket(b"[1, 2, 3]\n")
        select_mock.return_value = ([connection], [], [])
        client = {
            "conn": connection,
            "buffer": "",
            "output_buffer": bytearray(),
        }
        dispatched = []

        result = service_client(
            client,
            None,
            {},
            lambda message, *_: dispatched.append(message),
        )

        self.assertTrue(result)
        self.assertEqual(dispatched, [])
        response = json.loads(bytes(client["output_buffer"]).splitlines()[0])
        self.assertEqual(response["failure"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
