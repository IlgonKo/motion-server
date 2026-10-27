"""Tkinter view over the same Sequence; no socket work on the UI thread."""

from copy import deepcopy
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from motion_server_reference_client import MotionServerClient
from .program import Cancelled, Feedback, Sequence, capture, load_json, number, save_points, success


class Panel:
    def __init__(self, root, config_path, points_path):
        self.root = root
        self.config = load_json(config_path)
        self.points_path = points_path
        self.points = load_json(points_path) if self.config["teaching"] else {}
        self.client = self.feedback = self.sequence = None
        self.busy = False
        self.closing = False
        self.pending_stop = False
        self.jogging = False
        self.jog_release = threading.Event()
        self.events = queue.Queue()
        self.host = tk.StringVar(value=self.config["host"])
        self.port = tk.StringVar(value=str(self.config["port"]))
        self.status = tk.StringVar(value="Disconnected")
        self.phase = tk.StringVar(value="idle")
        root.title("Motion Server — AI Reference Pick & Place")
        connection = ttk.Frame(root)
        connection.pack(fill="x", padx=8, pady=8)
        ttk.Label(connection, text="Host").pack(side="left")
        ttk.Entry(connection, textvariable=self.host, width=18).pack(side="left")
        ttk.Label(connection, text="Port").pack(side="left")
        ttk.Entry(connection, textvariable=self.port, width=7).pack(side="left")
        self.connect_button = ttk.Button(connection, text="Connect", command=self.connect)
        self.connect_button.pack(side="left")
        self.disconnect_button = ttk.Button(connection, text="Disconnect", command=self.disconnect)
        self.disconnect_button.pack(side="left")
        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=8)
        self.request_button = ttk.Button(controls, text="Request Authority", command=lambda: self.authority("request"))
        self.request_button.pack(side="left")
        self.release_button = ttk.Button(controls, text="Release Authority", command=lambda: self.authority("release"))
        self.release_button.pack(side="left")
        self.run_button = ttk.Button(controls, text="Run once", command=self.run)
        self.run_button.pack(side="left")
        ttk.Button(controls, text="Stop", command=self.stop).pack(side="left")
        ttk.Label(root, textvariable=self.status, wraplength=850).pack(anchor="w", padx=8)
        ttk.Label(root, textvariable=self.phase).pack(anchor="w", padx=8)
        self.teaching_widgets = []
        self.motion_widgets = []
        if self.config["teaching"]:
            self.build_teaching()
        self.log = tk.Text(root, width=100, height=15, state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        root.bind("<FocusOut>", self.focus_out)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self.tick)

    def report(self, text):
        self.events.put(("log", str(text)))

    def submit(self, operation):
        if self.busy or self.closing:
            return
        self.busy = True
        def worker():
            try:
                operation()
            except Exception as exc:
                self.report(f"Failed: {exc}")
            finally:
                self.events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def connect(self):
        try:
            host, port = self.host.get(), int(self.port.get())
        except ValueError as exc:
            self.report(exc)
            return
        def operation():
            if self.client:
                self.shutdown_connection()
            self.client = MotionServerClient(host, port, request_timeout=self.config["request_timeout"])
            self.feedback = Feedback(self.client)
            self.client.start()
            self.feedback.start()
            if not self.client.wait_connected(timeout=self.config["request_timeout"]):
                raise RuntimeError(self.client.last_error)
            self.report("Connected; request authority explicitly")
        self.submit(operation)

    def shutdown_connection(self):
        try:
            if self.client and self.client.is_connected:
                value = self.feedback.snapshot()[2]
                if value and value.get("command_authority", {}).get("owned_by_this_client"):
                    success(self.client.request({"cmd": "system/authority/release"}))
        finally:
            if self.client:
                self.client.stop()
                self.feedback.close()
            self.client = self.feedback = None

    def disconnect(self):
        self.submit(self.shutdown_connection)

    def authority(self, action):
        self.submit(lambda: self.report(success(self.client.request({"cmd": f"system/authority/{action}"}))))

    def run(self):
        if self.busy or not self.feedback:
            return
        try:
            self.sequence = Sequence(self.client, self.feedback, self.config, self.points, self.report)
        except Exception as exc:
            self.report(exc)
            return
        self.submit(self.sequence.run)

    def stop(self):
        self.jog_release.set()
        if self.busy:
            if self.sequence and self.sequence.state in ("idle", "running", "stopping"):
                self.sequence.cancel.set()
            elif not self.jogging:
                self.pending_stop = True
            return
        # Explicit Stop while idle also applies to all configured sequence axes.
        if self.client:
            self.submit(self.manual_stop)

    def manual_stop(self, guard=None):
        guard = guard or Sequence(self.client, self.feedback, self.config, {}, self.report, manual=True)
        guard.checkpoint(cleanup=True)
        success(self.client.request({"cmd": "system/axes/stop", "axes": guard.axes}))
        guard.wait(lambda f: all(not f["statuswords"][a] & 256 for a in guard.axes),
                   self.feedback.snapshot()[0], self.config["stage_timeout"], cleanup=True)
        self.report("Standstill confirmed")

    def build_teaching(self):
        box = ttk.LabelFrame(self.root, text="Teaching — explicit Save; coordinates use configured API units")
        box.pack(fill="x", padx=8, pady=8)
        self.point_name = tk.StringVar(value=next(iter(self.points), "Pick"))
        self.point_select = ttk.Combobox(box, textvariable=self.point_name, values=list(self.points))
        self.point_select.grid(row=0, column=0)
        self.point_select.bind("<<ComboboxSelected>>", lambda _: self.load_editor())
        self.teaching_widgets.append(self.point_select)
        self.editor = tk.Text(box, width=65, height=6)
        self.editor.grid(row=1, column=0, columnspan=6, sticky="ew")
        self.teaching_widgets.append(self.editor)
        for i, (label, action) in enumerate((("Capture", self.capture_point), ("Add / Apply", self.apply_point),
                                            ("Delete", self.delete_point), ("Save file", self.save))):
            button = ttk.Button(box, text=label, command=action)
            button.grid(row=0, column=i+1)
            self.teaching_widgets.append(button)
        self.role = tk.StringVar(value=next(iter(self.config["roles"])))
        selector = ttk.Combobox(box, textvariable=self.role, values=list(self.config["roles"]), state="readonly", width=8)
        selector.grid(row=2, column=0)
        self.teaching_widgets.append(selector)
        for i, command in enumerate(("enable", "disable", "fault_reset", "home")):
            button = ttk.Button(box, text=command, command=lambda c=command: self.manual(c))
            button.grid(row=2, column=i+1)
            self.motion_widgets.append(button)
        self.speed = tk.StringVar(value="slow")
        ttk.Combobox(box, textvariable=self.speed, values=["slow", "fast"], state="readonly", width=8).grid(row=3, column=0)
        for i, direction in enumerate(("negative", "positive")):
            button = ttk.Button(box, text="Jog −" if i == 0 else "Jog +")
            button.grid(row=3, column=i+1)
            button.bind("<ButtonPress-1>", lambda _, d=direction: self.jog(d))
            button.bind("<ButtonRelease-1>", lambda _: self.jog_release.set())
            button.bind("<Leave>", lambda _: self.jog_release.set())
            self.motion_widgets.append(button)
        self.teach_values = {}
        for i, key in enumerate(("velocity", "acceleration", "deceleration")):
            value = tk.StringVar(value=str(self.config["teaching_motion"][key]))
            self.teach_values[key] = value
            ttk.Label(box, text=key).grid(row=4, column=i*2)
            entry = ttk.Entry(box, textvariable=value, width=9)
            entry.grid(row=4, column=i*2+1)
            self.teaching_widgets.append(entry)
        button = ttk.Button(box, text="Move to point", command=self.move_point)
        button.grid(row=3, column=3)
        self.motion_widgets.append(button)
        self.load_editor()

    def load_editor(self):
        if not self.busy:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", json.dumps(self.points.get(self.point_name.get(), {}), indent=2))

    def capture_point(self):
        try:
            point = capture(self.feedback, self.config)
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", json.dumps(point, indent=2))
        except Exception as exc:
            self.report(exc)

    def apply_point(self):
        try:
            point = json.loads(self.editor.get("1.0", "end"))
            name = self.point_name.get().strip()
            if not name:
                raise ValueError("Point name required")
            for role, axis in self.config["roles"].items():
                number(point[role]["position"], role)
                if point[role]["unit"] != axis["unit"]:
                    raise ValueError("Point unit mismatch")
            self.points[name] = point
            self.point_select.configure(values=list(self.points))
            self.report("Point applied in memory; Save file explicitly")
        except Exception as exc:
            self.report(exc)

    def delete_point(self):
        self.points.pop(self.point_name.get(), None)
        self.point_select.configure(values=list(self.points))
        self.report("Point deleted in memory; Save file explicitly")

    def save(self):
        try:
            save_points(self.points_path, self.points)
            self.report("Points saved (Apply editor first)")
        except Exception as exc:
            self.report(exc)

    def manual(self, command):
        axis = self.config["roles"][self.role.get()]["axis"]
        self.submit(lambda: self.report(success(self.client.request({"cmd": f"system/axis/{command}", "axis": axis}))))

    def jog(self, direction):
        if self.busy:
            return
        axis = self.config["roles"][self.role.get()]["axis"]
        speed = self.speed.get()
        self.jog_release.clear()
        self.jogging = True
        def operation():
            guard = Sequence(self.client, self.feedback, self.config, {}, self.report, manual=True)
            guard.checkpoint()
            try:
                success(self.client.request({"cmd": "system/axis/jog_start", "axis": axis, "direction": direction, "speed": speed}))
                guard.state = "running"
                guard.monitor_after = self.feedback.snapshot()[0]
                while not self.jog_release.wait(0.02):
                    guard.checkpoint()
            finally:
                guard.checkpoint(cleanup=True)
                success(self.client.request({"cmd": "system/axis/jog_stop", "axis": axis}))
                guard.wait(lambda f: not f["statuswords"][axis] & 256, self.feedback.snapshot()[0],
                           self.config["stage_timeout"], cleanup=True)
        self.submit(operation)

    def move_point(self):
        try:
            point = deepcopy(self.points[self.point_name.get()])
            settings = {k: number(float(v.get()), k, positive=True) for k, v in self.teach_values.items()}
            for role, axis in self.config["roles"].items():
                number(point[role]["position"], role)
                if point[role]["unit"] != axis["unit"]:
                    raise ValueError("Point unit mismatch")
            guard = Sequence(self.client, self.feedback, self.config, {}, self.report, manual=True)
            self.sequence = guard
        except Exception as exc:
            self.report(exc)
            return
        def operation():
            guard.state = "running"
            outcome = "completed"
            try:
                for role, axis in self.config["roles"].items():
                    guard.checkpoint()
                    success(self.client.request({"cmd": "system/axis/profile", "axis": axis["axis"],
                        "profile_acceleration": settings["acceleration"], "profile_deceleration": settings["deceleration"]}))
                guard.checkpoint()
                positions = [point[r]["position"] for r in self.config["roles"]]
                success(self.client.request({"cmd": "system/axes/move_abs", "axes": guard.axes,
                    "positions": positions, "profile_velocity": settings["velocity"]}))
                guard.monitor_after = self.feedback.snapshot()[0]
                guard.wait(lambda f: all(abs(f["actual_positions"][a]-p) <= self.config["position_tolerance"]
                    and abs(f["target_positions"][a]-p) <= self.config["position_tolerance"]
                    and f["statuswords"][a] & 1024 and not f["statuswords"][a] & 256
                    for a, p in zip(guard.axes, positions)), self.feedback.snapshot()[0], self.config["stage_timeout"])
            except Cancelled:
                outcome = "cancelled"
            except Exception:
                outcome = "failed"
                raise
            finally:
                guard.state = "stopping"
                try:
                    self.manual_stop(guard)
                except Exception:
                    outcome = "failed"
                    raise
                finally:
                    guard.state = outcome
        self.submit(operation)

    def focus_out(self, _):
        # Widget-to-widget focus changes may stop Jog too; never prolong a held command.
        self.jog_release.set()

    def close(self):
        self.stop()
        self.closing = True

    def tick(self):
        while True:
            try:
                event, value = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "done":
                self.busy = False
                self.jogging = False
            else:
                self.log.configure(state="normal")
                self.log.insert("end", value + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        if self.pending_stop and not self.busy:
            self.pending_stop = False
            closing = self.closing
            self.closing = False
            self.submit(self.manual_stop)
            self.closing = closing
        connected = bool(self.client and self.client.is_connected)
        snapshot = self.feedback.snapshot() if self.feedback else (0, 0, None, 0)
        value = snapshot[2] or {}
        fresh = time.monotonic() - snapshot[1] <= self.config["feedback_timeout"]
        owned = connected and fresh and value.get("command_authority", {}).get("owned_by_this_client", False)
        self.status.set(f"Connected: {connected} | Authority: {owned} | Feedback fresh: {fresh} | "
                        f"Server: {value.get('server_health', {})}\n"
                        f"Positions: {value.get('actual_positions', [])} | Referenced: "
                        f"{[bool(s & 32768) for s in value.get('statuswords', [])]}")
        if self.sequence:
            self.phase.set(f"{self.sequence.state}: {self.sequence.step}")
        for button, enabled in ((self.connect_button, not connected), (self.disconnect_button, connected),
                                (self.request_button, connected and not owned), (self.release_button, owned),
                                (self.run_button, owned)):
            button.configure(state="normal" if enabled and not self.busy and not self.closing else "disabled")
        for widget in self.teaching_widgets:
            widget.configure(state="disabled" if self.busy or self.closing else "normal")
        for widget in self.motion_widgets:
            widget.configure(state="normal" if owned and not self.busy and not self.closing else "disabled")
        if self.closing and not self.busy:
            self.closing = False
            self.submit(self.shutdown_connection)
            self.closing = True
            self.root.after(50, self.finish_close)
            return
        self.root.after(50, self.tick)

    def finish_close(self):
        # Continue pumping completion/log events while shutdown runs.
        try:
            while True:
                event, _ = self.events.get_nowait()
                if event == "done":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self.finish_close)


def show(config_path, points_path):
    root = tk.Tk()
    Panel(root, config_path, points_path)
    root.mainloop()
