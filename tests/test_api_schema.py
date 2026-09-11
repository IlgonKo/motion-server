import json
import shutil
import tempfile
import unittest
from pathlib import Path

from referencing.exceptions import Unresolvable

from motion_server.api.schema_loader import ApiContracts, SCHEMA_DIRECTORY, api_contracts
from motion_server.api.specification import command_spec


class ApiSchemaTests(unittest.TestCase):
    def test_authority_action_responses_match_existing_handlers(self):
        from motion_server.handlers.authority.registry import acquire_authority, release_authority
        from motion_server.api.encoder import ResponseContext, success_response
        state = {"command_authority_owner": None}
        client = {"id": 42}
        for name, operation in (("request", acquire_authority), ("release", release_authority)):
            command = f"system/authority/{name}"
            response = success_response(ResponseContext(command), operation(client, state, None))
            validator = api_contracts().response_validator(command)
            validator.validate(response)
            response["data"]["granted"] = "false"
            self.assertTrue(list(validator.iter_errors(response)))

    def test_validator_uses_schema_without_coercing_numeric_strings(self):
        from motion_server.api.validator import validate_command
        from motion_server.app.initialization import InitializationStatus
        from motion_server.failure import InvalidArgumentException
        state = {"initialization_status": InitializationStatus.ready()}
        name = "system/axis/param_read"
        request = {"cmd": name, "axis": 0, "index": 0x6081}
        self.assertIsNone(validate_command(command_spec(name), {}, state, True, message=request))
        for value in ("0x6081", True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(InvalidArgumentException):
                validate_command(command_spec(name), {}, state, True, message={**request, "index": value})

    def test_invalid_numeric_request_is_fail_before_handler_execution(self):
        from unittest.mock import patch
        from motion_server.api.router import route_message
        from motion_server.app.initialization import InitializationStatus
        state = {"initialization_status": InitializationStatus.ready(), "command_authority_owner": 1}
        client = {"id": 1, "output_buffer": bytearray()}
        with patch("motion_server.api.router.handle_status") as handler:
            response = route_message({"cmd": "system/axis/param_read", "axis": 0,
                                      "index": "0x6041", "request_id": "numeric-test"}, None, state, client)
        handler.assert_not_called()
        self.assertEqual(response["result"], "fail")
        self.assertEqual(response["failure"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(response["request_id"], "numeric-test")
        api_contracts().response_validator("system/axis/param_read").validate(response)

    def test_panel_parameter_inputs_are_json_numbers(self):
        from control_panel.axis_control_panel.client import AxisServerClient
        from control_panel.request_values import parameter_input
        client = AxisServerClient("127.0.0.1", 15000)
        messages = []
        client.send_json = messages.append
        client.send_param_write(0, "0x6081", "00", "uint32", "100", "4")
        self.assertEqual(messages[0]["index"], 0x6081)
        self.assertEqual(messages[0]["value"], 100)
        self.assertEqual(messages[0]["length"], 4)
        self.assertFalse(list(api_contracts().request_errors(messages[0]["cmd"], messages[0])))
        self.assertEqual(parameter_input("001122", "bytes"), "001122")
        self.assertEqual(parameter_input("100", "string"), "100")

    def test_actual_feedback_and_server_status_contract(self):
        from motion_server.app.session import ServerSession
        from motion_server.app.initialization import InitializationStatus
        from motion_server.diagnostic import DiagnosticManager
        from motion_server.handlers.status.feedback import system_feedback_message
        from motion_server.handlers.status.server_status import server_status_message
        from motion_server.api.encoder import ResponseContext, success_response, status_data
        manager = DiagnosticManager()
        session = ServerSession(InitializationStatus.ready(), diagnostic_manager=manager)
        state = {"server_session": session, "diagnostic_manager": manager,
                 "initialization_status": session.initialization_status}
        feedback = system_feedback_message(None, state)
        api_contracts().feedback_validator().validate(feedback)
        malformed = {**feedback, "actual_positions": ["1"]}
        self.assertTrue(list(api_contracts().feedback_validator().iter_errors(malformed)))
        response = success_response(ResponseContext("system/server/status"), status_data(server_status_message(None, state)))
        api_contracts().response_validator("system/server/status").validate(response)
        response["data"]["initialized"] = "yes"
        self.assertTrue(list(api_contracts().response_validator("system/server/status").iter_errors(response)))

    def test_actual_mock_io_snapshot_contract(self):
        from tests.test_virtual_cpx_ap import VirtualCpxRuntimeIntegrationTest
        from motion_server.handlers.status.io_input_read import input_read_data
        from motion_server.api.encoder import ResponseContext, success_response
        runtime = VirtualCpxRuntimeIntegrationTest().runtime()
        try:
            data = input_read_data({"io": "io0", "raw": True}, runtime)
            response = success_response(ResponseContext("system/io/input_read"), data)
            api_contracts().response_validator("system/io/input_read").validate(response)
        finally:
            runtime.close()

    def test_actual_mock_axis_status_and_feedback_contract(self):
        from types import SimpleNamespace
        from tests.test_virtual_cpx_ap import VirtualCpxRuntimeIntegrationTest
        from motion_server.app.state import initial_server_state
        from motion_server.app.session import ServerSession
        from motion_server.app.initialization import InitializationStatus
        from motion_server.diagnostic import DiagnosticManager
        from motion_server.handlers.status.axis_status import axis_status_message, axes_status_message
        from motion_server.handlers.status.feedback import system_feedback_message
        from motion_server.api.encoder import ResponseContext, success_response, status_data
        runtime = VirtualCpxRuntimeIntegrationTest().runtime()
        try:
            session = ServerSession(InitializationStatus.ready(), diagnostic_manager=DiagnosticManager(), runtime=runtime)
            server = SimpleNamespace(mode=SimpleNamespace(value="basic"), axis_restart_disable_settle_time=0,
                                     bus_reconnect_timeout=1, axis_restart_timeout=1)
            motion = SimpleNamespace(csp_interpolation_mode=4, initial_motion_mode="pp")
            state = initial_server_state(server, motion, True, 1, runtime.device_manager.axes, [0], server_session=session)
            for name, data in (("system/axis/status", axis_status_message(runtime, state, 0)),
                               ("system/axes/status", axes_status_message(runtime, state))):
                api_contracts().response_validator(name).validate(success_response(ResponseContext(name), status_data(data)))
            api_contracts().feedback_validator().validate(system_feedback_message(runtime, state))
        finally:
            runtime.close()

    def test_runtime_metadata_uses_existing_authority_and_recovery_contract(self):
        self.assertTrue(command_spec("system/axis/move_abs").authority_required)
        self.assertTrue(command_spec("system/axis/manualCW").advanced_only)
        self.assertTrue(command_spec("system/bus/reconnect").degraded_allowed)
        self.assertTrue(command_spec("system/io/ap/param_read").transport_required)
        self.assertFalse(command_spec("system/simulation/io/input_write").authority_required)
        self.assertIsNone(command_spec("system/bus/rescan"))
        self.assertIs(api_contracts(), api_contracts())

    def test_numeric_contract_rejects_strings_and_boolean(self):
        contract = api_contracts()
        name = "system/axis/move_abs"
        request = {"cmd": name, "axis": 0, "position": 10.5}
        self.assertEqual(list(contract.request_errors(name, request)), [])
        for field, value in (("axis", "0"), ("axis", True), ("position", "10.5"), ("position", False)):
            with self.subTest(field=field, value=value):
                self.assertTrue(list(contract.request_errors(name, {**request, field: value})))

    def test_nested_trajectory_numbers_are_typed(self):
        name = "system/axes/trajectory"
        request = {"cmd": name, "axes": [0], "points": [{"positions": [1], "time_from_start": 2}]}
        self.assertFalse(list(api_contracts().request_errors(name, request)))
        request["points"][0]["positions"] = ["1"]
        self.assertTrue(list(api_contracts().request_errors(name, request)))

    def test_required_member_and_typed_parameter_value(self):
        name = "system/axis/param_write"
        request = {"cmd": name, "axis": 0, "index": 0x6081, "data_type": "uint32", "value": 100}
        self.assertFalse(list(api_contracts().request_errors(name, request)))
        for changed in ({**request, "value": "100"}, {k: v for k, v in request.items() if k != "index"}):
            self.assertTrue(list(api_contracts().request_errors(name, changed)))

    def test_response_schema_is_not_a_runtime_validator(self):
        from motion_server.api.encoder import ResponseContext, success_response
        data = {"arbitrary_handler_field": 1}
        self.assertEqual(success_response(ResponseContext("example"), data)["data"], data)

    def test_invalid_reference_fails_without_network_retrieval(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copytree(SCHEMA_DIRECTORY, temp, dirs_exist_ok=True)
            path = Path(temp) / "common.json"
            document = json.loads(path.read_text())
            document["$defs"]["missing"] = {"$ref": "missing.json#/$defs/value"}
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(Unresolvable):
                ApiContracts(temp)

    def test_duplicate_command_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copytree(SCHEMA_DIRECTORY, temp, dirs_exist_ok=True)
            path = Path(temp) / "axis.json"
            document = json.loads(path.read_text())
            definition = document["$defs"]["system_axis_enable"]
            document["$defs"]["duplicate_enable"] = definition
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate API command"):
                ApiContracts(temp)

    def test_schema_bundle_loads_without_repository_relative_working_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "motion_server" / "api" / "schema"
            shutil.copytree(SCHEMA_DIRECTORY, destination)
            contract = ApiContracts(destination)
            self.assertEqual(set(contract.commands), set(api_contracts().commands))
            self.assertEqual(len(contract.commands), 57)

    def test_missing_required_metadata_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copytree(SCHEMA_DIRECTORY, temp, dirs_exist_ok=True)
            path = Path(temp) / "axis.json"
            document = json.loads(path.read_text())
            metadata = document["$defs"]["system_axis_enable"]["x-motion-server"]
            del metadata["authority_required"]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid authority_required"):
                ApiContracts(temp)

    def test_duplicate_json_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copytree(SCHEMA_DIRECTORY, temp, dirs_exist_ok=True)
            path = Path(temp) / "common.json"
            path.write_text('{"$defs": {}, "$defs": {}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate schema member"):
                ApiContracts(temp)


if __name__ == "__main__":
    unittest.main()
