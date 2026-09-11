"""A readable sequence, not a framework or a second set of Motion Server APIs."""

from copy import deepcopy
import json
import math
from pathlib import Path
import queue
import threading
import time


class Cancelled(Exception):
    pass


def success(response):
    # The official transport deliberately returns Fail envelopes unchanged.
    if response.get("result") != "success":
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response.get("data", {})


class Feedback:
    """One queue consumer for both GUI and sequence; local order is NOT a command ID."""

    def __init__(self, client):
        self.client = client
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.latest = None
        self.received = 0.0
        self.serial = 0
        self.loss = 0
        self.thread = threading.Thread(target=self._read, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.done.set()
        self.thread.join(timeout=1)

    def _read(self):
        connected = self.client.is_connected
        owned = False
        while not self.done.is_set():
            current = self.client.is_connected
            with self.lock:
                if connected and not current:
                    self.loss += 1
                    self.latest = None
                connected = current
            try:
                value = self.client.get_feedback(timeout=0.05)
            except queue.Empty:
                continue
            if not self.client.is_connected:
                continue
            now_owned = value.get("command_authority", {}).get("owned_by_this_client", False)
            with self.lock:
                if owned and not now_owned:
                    self.loss += 1
                owned = now_owned
                self.latest = value
                self.received = time.monotonic()
                self.serial += 1

    def snapshot(self):
        with self.lock:
            return self.serial, self.received, deepcopy(self.latest), self.loss


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_points(path, points):
    # Explicit user Save only; replace atomically rather than truncate an existing file.
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(points, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def number(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def prepare(config, points, *, manual=False):
    """Snapshot and validate our own data, never duplicate drive run interlocks."""
    c = deepcopy(config)
    roles = c["roles"]
    if not roles or len({v["axis"] for v in roles.values()}) != len(roles):
        raise ValueError("Roles must select distinct axes")
    for role, axis in roles.items():
        if type(axis["axis"]) is not int or axis["axis"] < 0 or not axis["unit"]:
            raise ValueError(f"Invalid axis/unit for {role}")
    for key in ("request_timeout", "feedback_timeout", "stage_timeout", "input_timeout", "position_tolerance"):
        number(c[key], key, positive=True)
    for role in roles:
        for key in ("acceleration", "deceleration"):
            number(c["profile"][role][key], key, positive=True)
    for name in (() if manual else ("pick", "place")):
        step = c[name]
        if c["teaching"]:
            point = points[step["point"]]
            step["positions"] = {}
            for role, axis in roles.items():
                if point[role]["unit"] != axis["unit"]:
                    raise ValueError(f"Point unit mismatch: {role}")
                step["positions"][role] = point[role]["position"]
        for role in roles:
            number(step["positions"][role], f"{name}.{role}")
            number(step["velocities"][role], f"{name}.{role}.velocity", positive=True)
    for key in ("grasp_outputs", "release_outputs", "failure_outputs"):
        for output in c[key]:
            for field in ("slot", "channel"):
                if type(output[field]) is not int or output[field] < 0:
                    raise ValueError(f"Invalid output {field}")
            if output["kind"] not in ("digital", "analog"):
                raise ValueError("This example supports digital/analog outputs")
            if type(output["value"]) is not (bool if output["kind"] == "digital" else int):
                raise ValueError("DO requires Boolean, AO requires raw integer")
    for key in ("grasp_conditions", "release_conditions"):
        for condition in c[key]:
            for field in ("slot", "channel"):
                if type(condition[field]) is not int or condition[field] < 0:
                    raise ValueError(f"Invalid input {field}")
            if condition["kind"] not in ("digital", "analog") or condition["op"] not in ("eq", "ge", "le"):
                raise ValueError("Invalid input condition")
            if type(condition["value"]) is not (bool if condition["kind"] == "digital" else int):
                raise ValueError("DI requires Boolean, AI requires raw integer")
    return c


def input_matches(feedback, conditions):
    for condition in conditions:
        try:
            station = next(d for d in feedback["io"]["devices"] if d["id"] == condition["io"])
            module = next(m for m in station["modules"] if m["slot"] == condition["slot"])
            value = module["inputs"][condition["kind"]][condition["channel"]]
        except (KeyError, IndexError, StopIteration):
            return False
        expected = condition["value"]
        if not {"eq": value == expected, "ge": value >= expected, "le": value <= expected}[condition["op"]]:
            return False
    return True


class Sequence:
    def __init__(self, client, feedback, config, points, report=print, *, manual=False):
        self.client, self.feedback = client, feedback
        self.config = prepare(config, points, manual=manual)
        self.report = report
        self.cancel = threading.Event()
        self.state = "idle"
        self.step = ""
        self.axes = [v["axis"] for v in self.config["roles"].values()]
        self.loss = feedback.snapshot()[3]
        self.monitor_after = None
        self.running = threading.Lock()

    def checkpoint(self, *, cleanup=False):
        if not cleanup and self.cancel.is_set():
            raise Cancelled("User Stop")
        serial, received, value, loss = self.feedback.snapshot()
        if (not self.client.is_connected or loss != self.loss or value is None
                or time.monotonic() - received > self.config["feedback_timeout"]):
            raise RuntimeError("Connection/Feedback lost; no automatic resume")
        if not value.get("command_authority", {}).get("owned_by_this_client"):
            raise RuntimeError("Authority lost; cleanup may be unavailable")
        if (not cleanup and self.state == "running" and self.monitor_after is not None
                and serial > self.monitor_after):
            if value.get("server_health", {}).get("fault_count", 0) or any(
                    value["statuswords"][a] & 8 for a in self.axes):
                raise RuntimeError("Fault detected during sequence")
        return serial, value

    def wait(self, predicate, after, timeout, *, cleanup=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            serial, value = self.checkpoint(cleanup=cleanup)
            if serial > after and value.get("process_data_valid") and predicate(value):
                return value
            time.sleep(0.02)
        raise TimeoutError(f"Condition timeout: {self.step}")

    def run(self):
        if not self.running.acquire(blocking=False):
            raise RuntimeError("Sequence already running")
        if self.state != "idle":
            self.running.release()
            raise RuntimeError("Create a new Run snapshot; do not resume")
        outcome = "completed"
        try:
            # No Homing/Enable/Fault/limit preflight. The API remains authoritative.
            self.checkpoint()
            self.state = "running"
            c = self.config
            self.step = "Common acceleration/deceleration"
            self.report(self.step)
            for role, axis in c["roles"].items():
                self.checkpoint()
                success(self.client.request({"cmd": "system/axis/profile", "axis": axis["axis"],
                    "profile_acceleration": c["profile"][role]["acceleration"],
                    "profile_deceleration": c["profile"][role]["deceleration"]}, timeout=c["request_timeout"]))
            for name, output_key, condition_key in (("pick", "grasp_outputs", "grasp_conditions"),
                                                    ("place", "release_outputs", "release_conditions")):
                self.step = f"Move {name}"
                self.report(self.step)
                self.checkpoint()
                positions = [c[name]["positions"][r] for r in c["roles"]]
                success(self.client.request({"cmd": "system/axes/move_abs", "axes": self.axes,
                    "positions": positions, "profile_velocities": [c[name]["velocities"][r] for r in c["roles"]]},
                    timeout=c["request_timeout"]))
                after = self.feedback.snapshot()[0]
                if self.monitor_after is None:
                    self.monitor_after = after
                self.wait(lambda f: all(abs(f["actual_positions"][a] - p) <= c["position_tolerance"]
                    and abs(f["target_positions"][a] - p) <= c["position_tolerance"]
                    and f["statuswords"][a] & (1 << 10) and not f["statuswords"][a] & (1 << 8)
                    for a, p in zip(self.axes, positions)), after, c["stage_timeout"])
                self.step = output_key
                self.report(self.step)
                for output in c[output_key]:
                    self.checkpoint()
                    success(self.client.request({"cmd": "system/io/output_write", **output}, timeout=c["request_timeout"]))
                if c[condition_key]:
                    self.step = condition_key
                    self.report(self.step)
                    self.wait(lambda f: input_matches(f, c[condition_key]), self.feedback.snapshot()[0], c["input_timeout"])
            self.checkpoint()
        except Cancelled as exc:
            outcome = "cancelled"
            self.report(str(exc))
        except Exception as exc:
            outcome = "failed"
            self.report(f"{self.step}: {exc}")
        finally:
            self.state = "stopping"
            self.step = "Cleanup"
            if self.cancel.is_set() and outcome == "completed":
                outcome = "cancelled"
            try:
                self.checkpoint(cleanup=True)
                success(self.client.request({"cmd": "system/axes/stop", "axes": self.axes}, timeout=self.config["request_timeout"]))
                self.wait(lambda f: all(not f["statuswords"][a] & (1 << 8) for a in self.axes),
                          self.feedback.snapshot()[0], self.config["stage_timeout"], cleanup=True)
            except Exception as exc:
                self.report(f"Stop NOT confirmed: {exc}")
                outcome = "failed"
            if self.cancel.is_set() and outcome == "completed":
                outcome = "cancelled"
            if outcome != "completed":
                for output in self.config["failure_outputs"]:
                    try:
                        self.checkpoint(cleanup=True)
                        success(self.client.request({"cmd": "system/io/output_write", **output}, timeout=self.config["request_timeout"]))
                    except Exception as exc:
                        self.report(f"I/O cleanup NOT confirmed: {exc}")
                        outcome = "failed"
            self.state = outcome
            self.report(outcome)
            self.running.release()
        return outcome


def capture(feedback, config):
    _, received, value, _ = feedback.snapshot()
    if (not feedback.client.is_connected or not value or not value.get("process_data_valid")
            or time.monotonic() - received > config["feedback_timeout"]):
        raise ValueError("Fresh valid Feedback required for capture")
    return {role: {"position": value["actual_positions"][axis["axis"]], "unit": axis["unit"]}
            for role, axis in config["roles"].items()}
