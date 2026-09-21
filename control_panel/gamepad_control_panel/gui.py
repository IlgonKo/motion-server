import tkinter as tk
from tkinter import ttk


class PendantWindow:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.connection = tk.StringVar(value="Server: Disconnected")
        self.gamepad = tk.StringVar(value="Gamepad: waiting")
        self.authority = tk.StringVar(value="Authority: unknown")
        self.operation = tk.StringVar(value="State: Disconnected")
        self.mode = tk.StringVar(value="Mode: multi")
        self.scale = tk.StringVar(value="Scale: 0")
        self.axes = tk.StringVar(value="Axis feedback: waiting")
        self.notice = tk.StringVar(value="")
        self.error = tk.StringVar(value="")

        root.title("Motion Server Gamepad Control Panel")
        root.geometry("700x360")
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        for variable in (
            self.connection,
            self.gamepad,
            self.authority,
            self.operation,
            self.mode,
            self.scale,
            self.axes,
        ):
            ttk.Label(frame, textvariable=variable).pack(anchor="w", pady=3)
        ttk.Separator(frame).pack(fill="x", pady=8)
        ttk.Label(frame, textvariable=self.notice, wraplength=650).pack(anchor="w", pady=3)
        ttk.Label(frame, textvariable=self.error, foreground="#b00020", wraplength=650).pack(
            anchor="w", pady=3
        )
        root.protocol("WM_DELETE_WINDOW", self.close)
        controller.start()
        root.after(50, self.refresh)

    def refresh(self):
        status = self.controller.status()
        snapshot = self.controller.input.snapshot()
        feedback = self.controller.feedback
        self.connection.set(
            "Server: Connected / Heartbeat active"
            if self.controller.client.is_connected
            else f"Server: Disconnected ({self.controller.client.last_error})"
        )
        self.gamepad.set(
            f"Gamepad: {snapshot.name} [{snapshot.guid}]"
            if snapshot.connected
            else f"Gamepad: {snapshot.error or 'waiting'}"
        )
        self.authority.set(f"Authority: {status.authority}")
        self.operation.set(f"State: {status.state}")
        self.mode.set(f"Mode: {status.mode} / selected Axis {status.selected_axis}")
        self.scale.set(
            "Jog speed: slow"
            if status.mode == "single"
            else f"Speed scale: {status.speed_scale:g}"
        )
        words = list(feedback.get("statuswords", []))
        axis_values = []
        for index, word in enumerate(words):
            enabled = int(word) & 0x006F == 0x0027
            standstill = not int(word) & (1 << 8)
            fault = bool(int(word) & (1 << 3))
            axis_values.append(
                f"{index}: {'Enabled' if enabled else 'Disabled'}, "
                f"{'Standstill' if standstill else 'Moving'}, "
                f"{'Fault' if fault else 'OK'}"
            )
        self.axes.set("Axis feedback: " + (" | ".join(axis_values) if axis_values else "waiting"))
        self.notice.set(status.last_notice)
        self.error.set(status.last_error)
        self.root.after(50, self.refresh)

    def close(self):
        self.controller.stop()
        self.root.destroy()


def show(controller):
    root = tk.Tk()
    PendantWindow(root, controller)
    root.mainloop()
