import tkinter as tk
from tkinter import ttk


def control_assignments(config):
    """Rows for every logical control in the selected device profile."""
    assigned = {control: action for action, control in config.actions.items()}
    assigned[config.enable_input.control] = "enable"
    rows = []
    for name, index in config.buttons.items():
        rows.append((name, f"button {index}", assigned.get(name, "Unassigned")))
    for name, index in config.trigger_axes.items():
        rows.append((name, f"axis {index}", assigned.get(name, "Unassigned")))
    for direction in ("up", "down", "left", "right"):
        physical = (
            f"hat {config.hat}"
            if config.hat is not None
            else f"button {config.dpad_buttons[direction]}"
        )
        name = f"dpad_{direction}"
        rows.append((name, physical, assigned.get(name, "Unassigned")))
    return rows


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
        root.geometry("700x590")
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
        ttk.Label(frame, text="Available controls and assigned functions").pack(
            anchor="w", pady=(10, 3)
        )
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        controls = ttk.Treeview(
            table_frame, columns=("physical", "action"), show="tree headings", height=12
        )
        controls.heading("#0", text="Control")
        controls.heading("physical", text="Device input")
        controls.heading("action", text="Function")
        controls.column("#0", width=150, stretch=False)
        controls.column("physical", width=150, stretch=False)
        controls.column("action", width=280)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=controls.yview)
        controls.configure(yscrollcommand=scrollbar.set)
        controls.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for name, physical, action in control_assignments(controller.config):
            controls.insert("", "end", text=name, values=(physical, action))
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
