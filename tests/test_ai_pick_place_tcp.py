"""S04: isolated real Mock backend + actual TCP client, never the user's server."""
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference_clients/python"))
from motion_server_reference_client import MotionServerClient
from examples.pick_place.program import Feedback, Sequence, load_json, success
from motion_server.api.schema_loader import api_contracts


class PickPlaceTcpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="motion-server-s04-")
        self.folder = Path(self.directory.name)
        package = os.environ.get("S04_PACKAGE_ROOT")
        if package:
            shutil.copytree(package, self.folder, dirs_exist_ok=True)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        config = f"""MOTION_SERVER_BACKEND=mock
MOTION_SERVER_MODE=basic
MOTION_SERVER_PORT={self.port}
MOTION_SERVER_BUS=cmmt_as,cmmt_as,cmmt_as,io:cpx_ap_i_ec:io0
MOTION_SERVER_CMMT_SLAVE_NON_PDO_CONFIGURATIONS=0:linear_mm,1:linear_mm,2:linear_mm
MOTION_SERVER_IO_io0_MODULES=1:do:8,2:aio:4:4,3:di:8,4:ai:4
MOTION_SERVER_MOTION_MODE=pp
MOTION_SERVER_FEEDBACK_PERIOD=0.01
MOTION_SERVER_COMMAND_LOGS=1
PYSOEM_DC_ENABLED=0
PYSOEM_CYCLE_TIME=0.008
"""
        (self.folder / ".env").write_text(config, encoding="utf-8")
        if package:
            (self.folder / "config.txt").write_text(config, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith(
            ("MOTION_SERVER_", "PYSOEM_", "MOCK_", "AXIS_"))}
        env["PYTHONPATH"] = "" if package else str(ROOT)
        code = ("from pathlib import Path; from configuration import ConfigurationSource; "
                "from motion_server.application import MotionServerApplication; "
                "import sys; MotionServerApplication.from_source("
                "ConfigurationSource(project_root=Path(sys.argv[1])), argv=[]).run()")
        if getattr(self, "inject_wkc", False):
            if package:
                self.directory.cleanup()
                self.skipTest("Test-only WKC hook requires source launcher")
            code = '''from pathlib import Path
import sys
from configuration import ConfigurationSource
from motion_server.application import MotionServerApplication
from motion_server.diagnostic.runtime import RuntimeDiagnosticMonitor
original = RuntimeDiagnosticMonitor.update
def update(self, runtime, **kwargs):
    if (Path(sys.argv[1]) / "inject-wkc").exists():
        runtime.wkc = 0
    return original(self, runtime, **kwargs)
RuntimeDiagnosticMonitor.update = update
MotionServerApplication.from_source(ConfigurationSource(project_root=Path(sys.argv[1])), argv=[]).run()
'''
        self.log = (self.folder / "server.log").open("w+", encoding="utf-8")
        command = [str(self.folder / "motion_server.exe")] if package else [sys.executable, "-u", "-c", code, str(self.folder)]
        self.process = subprocess.Popen(command,
            cwd=self.folder, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        client_port = self.start_proxy(self.port) if hasattr(self, "start_proxy") else self.port
        self.client = MotionServerClient("127.0.0.1", client_port, request_timeout=3)
        self.client.start()
        self.feedback = Feedback(self.client)
        self.feedback.start()
        try:
            self.assertTrue(self.client.wait_connected(10))
            status = success(self.client.request({"cmd": "system/server/status"}))
            self.assertTrue(status["initialized"], status)
            success(self.client.request({"cmd": "system/authority/request"}))
            self.wait_for(lambda f: f["command_authority"]["owned_by_this_client"])
            # Evaluator commissioning only; the generated/reference sequence must NOT do this.
            for axis in range(3):
                success(self.client.request({"cmd": "system/axis/enable", "axis": axis}))
            self.wait_for(lambda f: all(s & 0x006f == 0x27 for s in f["statuswords"]))
            for axis in range(3):
                success(self.client.request({"cmd": "system/axis/home", "axis": axis}))
                self.wait_for(lambda f, a=axis: bool(f["statuswords"][a] & 32768))
            self.config = load_json(ROOT / "reference_clients/python/examples/pick_place/sequence.json")
            self.config.update(stage_timeout=5, input_timeout=.3, feedback_timeout=1, port=self.port)
            self.config["pick"]["positions"] = {"X": .5, "Y": .6, "Z": .7}
            self.config["place"]["positions"] = {"X": 1., "Y": 1.1, "Z": 1.2}
            self.messages = []
            self.logs = []
            request = self.client.request
            def recorded(message, **kwargs):
                self.messages.append(dict(message))
                response = request(message, **kwargs)
                api_contracts().response_validator(message["cmd"]).validate(response)
                return response
            self.client.request = recorded
        except Exception:
            self.cleanup()
            raise

    def wait_for(self, condition, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            f = self.feedback.snapshot()[2]
            if f and f.get("process_data_valid") and condition(f):
                return f
            time.sleep(.01)
        raise AssertionError(f"Feedback timeout: {self.feedback.snapshot()[2]}")

    def cleanup(self):
        self.client.stop()
        self.feedback.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.seek(0)
        log = self.log.read()
        self.log.close()
        if hasattr(self, "_outcome") and self._outcome and not self._outcome.success:
            print(log[-6000:])
        self.directory.cleanup()

    def tearDown(self):
        self.cleanup()

    def set_inputs(self):
        for slot, kind, value in ((3, "digital", True), (4, "analog", 100)):
            success(self.client.request({"cmd": "system/simulation/io/input_write", "io": "io0",
                                         "slot": slot, "kind": kind, "channel": 0, "value": value}))
        self.messages.clear()

    def test_normal_actual_tcp_and_mock_motion(self):
        self.set_inputs()
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        self.assertEqual(seq.run(), "completed", self.logs)
        f = self.feedback.snapshot()[2]
        self.assertTrue(all(abs(p-t) < .01 for p,t in zip(f["actual_positions"], [1.,1.1,1.2])))
        self.assertTrue(all(s & 0x006f == 0x27 for s in f["statuswords"]))
        self.assertEqual(sum(m["cmd"] == "system/axes/move_abs" for m in self.messages), 2)
        self.assertFalse(any("disable" in m["cmd"] for m in self.messages))

    def test_input_timeout_no_place(self):
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        self.assertEqual(seq.run(), "failed", self.logs)
        self.assertEqual(sum(m["cmd"] == "system/axes/move_abs" for m in self.messages), 1)

    def test_api_fail_and_numeric_rejection(self):
        response = self.client.request({"cmd": "system/axis/status", "axis": "0"})
        self.assertEqual(response["result"], "fail")
        self.assertEqual(response["failure"]["code"], "INVALID_ARGUMENT")
        success(self.client.request({"cmd": "system/axis/disable", "axis": 1}))
        self.wait_for(lambda f: f["statuswords"][1] & 0x006f != 0x27)
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        self.assertEqual(seq.run(), "failed", self.logs)
        self.assertFalse(any(m["cmd"] == "system/io/output_write" for m in self.messages))

    def test_connection_loss_during_input_wait(self):
        self.loss_during_input_wait(disconnect=True)

    def test_authority_loss_during_input_wait(self):
        self.loss_during_input_wait(disconnect=False)

    def loss_during_input_wait(self, disconnect):
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        seq.config["input_timeout"] = 5
        worker = threading.Thread(target=seq.run)
        worker.start()
        end = time.monotonic()+5
        while seq.step != "grasp_conditions" and worker.is_alive() and time.monotonic()<end:
            time.sleep(.01)
        if disconnect:
            self.client.stop()
        else:
            success(self.client.request({"cmd": "system/authority/release"}))
        worker.join(6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seq.state, "failed", self.logs)
        self.assertEqual(sum(m["cmd"] == "system/axes/move_abs" for m in self.messages), 1)
        self.assertTrue(any("NOT confirmed" in line for line in self.logs))

    def test_stop_during_input_wait(self):
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        seq.config["input_timeout"] = 5
        worker = threading.Thread(target=seq.run)
        worker.start()
        end = time.monotonic()+5
        while seq.step != "grasp_conditions" and worker.is_alive() and time.monotonic()<end:
            time.sleep(.01)
        seq.cancel.set()
        worker.join(6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seq.state, "cancelled", self.logs)
        self.assertEqual(sum(m["cmd"] == "system/axes/move_abs" for m in self.messages), 1)
