"""Offline reference-program tests. These do not stand in for S04 independent AI evaluation."""

from copy import deepcopy
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference_clients" / "python"))
from examples.pick_place.program import Feedback, Sequence, capture, input_matches, load_json, prepare, save_points
from motion_server.api.schema_loader import api_contracts

EXAMPLE = ROOT / "reference_clients/python/examples/pick_place"


class FakeClient:
    """Deterministic simulated responses/feedback, no network or hardware access."""
    def __init__(self):
        self.is_connected = True
        self.requests = []
        self.queue = queue.Queue()
        self.value = {"process_data_valid": True, "actual_positions": [0., 0., 0.],
                      "target_positions": [0., 0., 0.], "statuswords": [1024]*3,
                      "command_authority": {"owned_by_this_client": True}, "server_health": {"fault_count": 0},
                      "io": {"devices": [{"id": "io0", "modules": [
                          {"slot": 3, "inputs": {"digital": [True]}},
                          {"slot": 4, "inputs": {"analog": [100]}}]}]}}
        self.hook = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self.pump, daemon=True)
        self.thread.start()

    def pump(self):
        while not self.done.wait(.005):
            self.queue.put(deepcopy(self.value))

    def get_feedback(self, timeout):
        return self.queue.get(timeout=timeout)

    def request(self, message, **kwargs):
        errors = list(api_contracts().request_errors(message["cmd"], message))
        if errors:
            raise AssertionError(errors)
        self.requests.append(deepcopy(message))
        if self.hook:
            result = self.hook(message)
            if result is not None:
                return result
        if message["cmd"] == "system/axes/move_abs":
            self.value["target_positions"] = list(message["positions"])
            self.value["actual_positions"] = list(message["positions"])
        return {"result": "success", "data": {}}

    def close(self):
        self.done.set()
        self.thread.join()


class PickPlaceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_json(EXAMPLE / "sequence.json")
        self.config.update(stage_timeout=.15, input_timeout=.15, feedback_timeout=.1)
        self.client = FakeClient()
        self.feedback = Feedback(self.client)
        self.feedback.start()
        deadline = time.monotonic()+1
        while not self.feedback.snapshot()[2] and time.monotonic() < deadline:
            time.sleep(.005)
        self.logs = []

    def tearDown(self):
        self.client.close()
        self.feedback.close()

    def sequence(self, **kwargs):
        return Sequence(self.client, self.feedback, self.config, kwargs.get("points", {}), self.logs.append)

    def test_normal_order_numeric_schema_and_no_wrapper_recovery_or_disable(self):
        self.assertEqual(self.sequence().run(), "completed")
        commands = [r["cmd"] for r in self.client.requests]
        self.assertEqual(commands, ["system/axis/profile"]*3 + ["system/axes/move_abs"] +
                         ["system/io/output_write"]*2 + ["system/axes/move_abs"] +
                         ["system/io/output_write"]*2 + ["system/axes/stop"])
        self.assertEqual(self.client.requests[3]["profile_velocities"], [5., 5., 2.])

    def test_fail_stops_without_retry_or_later_steps(self):
        self.client.hook = lambda m: {"result": "fail", "failure": {"code": "NOT_REFERENCED"}} if m["cmd"].endswith("move_abs") else None
        self.assertEqual(self.sequence().run(), "failed")
        self.assertEqual(sum(m["cmd"].endswith("move_abs") for m in self.client.requests), 1)
        self.assertFalse(any(m["cmd"].endswith("output_write") for m in self.client.requests))
        self.assertTrue(any("NOT_REFERENCED" in m for m in self.logs))

    def test_cancel_during_request_does_not_advance(self):
        seq = self.sequence()
        def hook(m):
            if m["cmd"].endswith("move_abs"):
                seq.cancel.set()
        self.client.hook = hook
        self.assertEqual(seq.run(), "cancelled")
        self.assertFalse(any(m["cmd"].endswith("output_write") for m in self.client.requests))

    def test_input_timeout_no_place_and_preserves_unspecified_outputs(self):
        self.client.value["io"]["devices"][0]["modules"][0]["inputs"]["digital"] = [False]
        self.assertEqual(self.sequence().run(), "failed")
        self.assertEqual(sum(m["cmd"].endswith("move_abs") for m in self.client.requests), 1)
        self.assertEqual(sum(m["cmd"].endswith("output_write") for m in self.client.requests), 2)

    def test_request_exception_stops_and_reports_unknown_result(self):
        def hook(m):
            if m["cmd"].endswith("move_abs"):
                raise TimeoutError("Request result unknown")
        self.client.hook = hook
        self.assertEqual(self.sequence().run(), "failed")
        self.assertTrue(any("unknown" in line for line in self.logs))
        self.assertEqual(self.client.requests[-1]["cmd"], "system/axes/stop")

    def test_initial_fault_is_not_a_duplicate_run_interlock(self):
        self.client.value["statuswords"] = [8]*3
        time.sleep(.03)
        self.client.hook = lambda m: {"result": "fail", "failure": {"code": "AXIS_FAULT"}} if m["cmd"].endswith("move_abs") else None
        self.assertEqual(self.sequence().run(), "failed")
        self.assertTrue(any(m["cmd"].endswith("move_abs") for m in self.client.requests))
        self.assertTrue(any("AXIS_FAULT" in line for line in self.logs))

    def test_fault_after_success_aborts_and_stops(self):
        def hook(m):
            if m["cmd"].endswith("move_abs"):
                self.client.value["statuswords"] = [8]*3
        self.client.hook = hook
        self.assertEqual(self.sequence().run(), "failed")
        self.assertTrue(any("Fault detected" in line for line in self.logs))
        self.assertFalse(any(m["cmd"].endswith("output_write") for m in self.client.requests))

    def test_invalid_or_partial_feedback_never_completes(self):
        for invalid in (True, False):
            with self.subTest(invalid=invalid):
                def hook(m):
                    if m["cmd"].endswith("move_abs"):
                        if invalid:
                            self.client.value["process_data_valid"] = False
                        else:
                            self.client.value["actual_positions"] = [10,20,0]
                            self.client.value["target_positions"] = [10,20,5]
                        return {"result": "success"}
                self.client.hook = hook
                self.client.value["process_data_valid"] = True
                self.assertEqual(self.sequence().run(), "failed")
        self.assertFalse(any(m["cmd"].endswith("output_write") for m in self.client.requests))

    def test_disconnect_or_authority_loss_no_cleanup_replay(self):
        for disconnect in (True, False):
            with self.subTest(disconnect=disconnect):
                self.client.is_connected = True
                self.client.value["command_authority"]["owned_by_this_client"] = True
                time.sleep(.03)
                def hook(m):
                    if m["cmd"].endswith("move_abs"):
                        if disconnect:
                            self.client.is_connected = False
                        else:
                            self.client.value["command_authority"]["owned_by_this_client"] = False
                        time.sleep(.03)
                self.client.hook = hook
                self.client.requests.clear()
                self.assertEqual(self.sequence().run(), "failed")
                self.assertFalse(any(m["cmd"].endswith("stop") for m in self.client.requests))
                self.assertTrue(any("NOT confirmed" in m for m in self.logs))

    def test_stale_feedback_does_not_complete_and_loss_latches(self):
        self.client.close()
        time.sleep(.15)
        seq = self.sequence()
        with self.assertRaises(RuntimeError):
            seq.checkpoint()
        with self.feedback.lock:
            self.feedback.received = time.monotonic()
            self.feedback.loss += 1
        with self.assertRaises(RuntimeError):
            seq.checkpoint()

    def test_snapshot_points_units_capture_save_and_missing_point(self):
        self.config["teaching"] = True
        points = load_json(EXAMPLE / "teaching_points.json")
        seq = self.sequence(points=points)
        points["Pick"]["X"]["position"] = 999
        self.assertEqual(seq.config["pick"]["positions"]["X"], 10)
        captured = capture(self.feedback, self.config)
        self.assertEqual(captured["X"], {"position": 0, "unit": "mm"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"teaching_points.json"
            save_points(path, {"New": captured})
            self.assertEqual(load_json(path), {"New": captured})
        with self.assertRaises(KeyError):
            self.sequence(points={})
        points["Pick"]["X"]["unit"] = "deg"
        with self.assertRaises(ValueError):
            self.sequence(points=points)
        # Missing sequence points must not prevent manual Teaching or Stop.
        Sequence(self.client, self.feedback, self.config, {}, manual=True)

    def test_duplicate_run_no_second_execution(self):
        seq = self.sequence()
        self.assertEqual(seq.run(), "completed")
        count = len(self.client.requests)
        with self.assertRaises(RuntimeError):
            seq.run()
        self.assertEqual(len(self.client.requests), count)

    def test_gui_constructs_without_connecting_or_sending_commands(self):
        import tkinter as tk
        from examples.pick_place.gui import Panel
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk display unavailable")
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/"sequence.json"
                config = deepcopy(self.config)
                config["teaching"] = True
                path.write_text(json.dumps(config), encoding="utf-8")
                panel = Panel(root, path, EXAMPLE/"teaching_points.json")
                root.update()
                self.assertIsNone(panel.client)
                self.assertFalse(panel.busy)
                panel.client, panel.feedback = self.client, self.feedback
                panel.jog("positive")
                panel.jog_release.set()
                deadline = time.monotonic()+2
                while panel.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertFalse(panel.busy)
                self.assertEqual([m["cmd"] for m in self.client.requests],
                                 ["system/axis/jog_start", "system/axis/jog_stop"])
                panel.run()
                panel.stop()
                deadline = time.monotonic()+2
                while panel.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(.01)
                self.assertFalse(panel.busy)
                self.assertEqual(panel.sequence.state, "cancelled")
                panel.focus_out(None)
                self.assertTrue(panel.jog_release.is_set())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
