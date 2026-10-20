# Motion Server Gamepad Control Panel

This Windows control panel reads DualSense and other SDL-compatible controllers through the stable
`pygame-ce` `pygame.joystick` API. It sends only existing Motion Server TCP commands and shows connection,
Heartbeat, authority, operating mode, speed scale, and Axis state in a small Tkinter window.
The window also lists every logical button, trigger, and D-pad direction in the selected profile, its
physical SDL input, and its assigned function. Unused controls appear as `Unassigned`; they do not need
empty entries in `config.json`.

## Install and configure

```powershell
python -m pip install -r requirements.txt
.\scripts\windows\gamepad.ps1 -ListDevices
```

Put the exact `name` and `guid` reported by `--list-devices` in `config.json` and select a bundled device
profile by name. Physical SDL axis/button numbers live in `device_profiles.json`, not in the operating
configuration. They can differ by connection type and GUID, so verify or add a profile for the intended USB
or Bluetooth setup before enabling real hardware. `server.axes` assigns X/Y/Z/Rotation roles to Motion
Server Axis indices, while root `axes` assigns those roles to logical stick names exposed by the profile. Also set
direction inversion and speed scales. Multi-mode velocity uses each Axis maximum from the server's
`motion_limits`; the Gamepad config does not duplicate those limits. Startup validation rejects unknown profiles, duplicate Axis indices,
duplicate logical inputs, and malformed values; arming additionally checks server topology, linear/rotary
role, and server motion limits.

`server.axes` always lists `x`, `y`, `z`, and `rotation`. Set an unused role to JSON `null` to control
any 1–4 axes; at least one role must have a unique server Axis index. For example,
`"axes": {"x": 2, "y": 1, "z": 0, "rotation": null}` controls three axes. Root `axes` and `invert`
still list all four roles, but unused roles never produce motion commands or require valid motion limits.
The all-Axis Stop action and all-Axis Standstill check still cover every server Axis. The bundled
example retains all four active roles.

The bundled `dualsense_windows` profile maps L1/R1 as buttons 9/10, L3/R3 as buttons 7/8, and the analog
L2/R2 triggers as axes 4/5. It also uses Cross button 0, Options 6, Create 4, Touchpad 15, and D-pad buttons
11–14. SDL reports this device with zero hats, so the profile sets `hat` to `null` and uses `dpad_buttons`.
Controllers that expose a real hat can set its index in `hat` and omit `dpad_buttons`.
After finding the configured device, the client checks every profile index against its reported axis,
button, and hat counts before accepting input. A mismatch is shown as a Gamepad error and blocks arming.

The root-level `actions` object assigns every operational function to a logical control exposed by the
selected device profile. `enable` accepts an analog trigger definition with `threshold` and `pressed_when`,
or a digital button with only `control`. All other actions use digital control names. Defaults include L2 for
Enable, Options for authority request/release, Touchpad for mode switching, Cross for Homing, and D-pad
directions for speed and selected-Axis changes. Controls must be unique so one press cannot invoke two actions.

On the first normal run, `gamepad.ps1` creates `config.json` from `config.example.json` when it is missing.
The generated file contains device identity placeholders and must be reviewed before arming. The adjacent
`device_profiles.json` is a device support catalog rather than an operating configuration.

Run:

```powershell
.\scripts\windows\gamepad.ps1
```

Use `-Config C:\path\to\config.json` to select another configuration file. The script adds the shared Python
client source root to `PYTHONPATH`, matching the direct Windows launch flow used by the Axis and I/O panels.

The client never requests authority or arms automatically after startup or reconnection. Press the configured
authority button (Options by default) to
request authority, release the Enable trigger with all sticks neutral, then hold L2 past the configured
threshold to enable the mapped Axis set. Releasing it immediately sends Disable/Quick Stop. Returning all
sticks to neutral sends Stop and remains Armed while the Enable trigger stays held.

Multi mode changes the mapped axes to PV while arming and uses `system/axes/move_vel`. Single mode enables
only the selected Axis and uses slow `system/axis/jog_start`/`jog_stop` from Left Stick Y; it never sends
`move_vel`. The emitted Jog direction is the reverse of the raw Left Stick Y sign for every selected Axis;
stick up sends `positive` and stick down sends `negative`. The Multi-mode role `invert` settings are not
applied to Single Jog. In Single mode,
stick neutral sends `jog_stop` and D-pad left/right changes the selected Axis only
while Disarmed, neutral, and all axes are Standstill.

In Single mode, press the configured Homing button while Armed, holding the Enable trigger, with all sticks
neutral and every Axis Standstill to
home the selected Axis. Jog input is suppressed while homing is active. The client polls
`system/axis/status` until homing completes; releasing the Enable trigger during homing immediately sends Disable/Quick Stop.
The Homing button is rejected in Multi mode.

## Windows executable

Use the common Windows package build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\build_exe.ps1
```

The normal Windows package build also creates `Tools\gamepad_control_panel\gamepad_control_panel.exe` and places
`config.example.json` and `device_profiles.json` beside it. Copy the example to `config.json` and review the
device identity, selected profile, and functional settings before running. PyInstaller includes the
pygame-ce SDL runtime in that directory.

This is a convenience pendant, not a safety-rated control. The first release intentionally does not detect
loss of the controller's USB/Bluetooth link or input-loop freshness; the common TCP Heartbeat protects the
Motion Server connection.
