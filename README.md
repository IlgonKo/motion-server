# Motion Server

**Build motion and I/O applications through a common API, using a PC as the EtherCAT host.**

Motion Server connects your application to servo drives and I/O devices through a
TCP JSON API. Combine motion commands, digital and analog I/O, and device parameter
access to create your own sequences with Python, Node-RED, or another TCP client.
It provides a PC-based control interface without requiring a separate dedicated
motion controller; compatible EtherCAT devices and network hardware are still required.

## What you can do

- **Control motion:** enable axes, move to positions, command velocity, jog, home, and stop.
- **Work with I/O:** read and write digital/analog signals and access CPX AP and IO-Link parameters.
- **Develop with virtual devices:** use the same API with virtual CMMT axes and CPX I/O,
  then connect your application to supported physical devices.
- **Inspect and configure:** use the Axis and I/O Control Panels for operation,
  device parameters, server status, and diagnostics.
- **Build application sequences:** use the Python reference client and Node-RED nodes,
  sample flows, and Dashboards as starting points.

```text
Your application / Python / Node-RED / Control Panels
                         |
                    TCP JSON API
                         |
                    Motion Server
                         |
          +--------------+--------------+
          |                             |
   Physical EtherCAT devices      Virtual devices
   CMMT-AS/ST + CPX-AP-I-EC       CMMT axes + CPX I/O
```

## Platforms and release status

- **Windows:** executable package or source execution, with optional Windows service registration.
- **Linux:** Docker deployment on the EtherCAT host PC.
- **Version 1.0:** internal and DT Demo development baseline. Final package validation
  and clean Windows/Linux environment acceptance remain pending.
- Windows CSP and synchronous control are not officially supported. Virtual-device
  testing does not establish physical-device timing or performance.

See the [1.0 release scope and remaining validation](docs/release_1.0.md).

## Getting started

1. Follow the [installation guide](docs/Motion_Server_Installation_Manual_Basic_Mode.md)
   to prepare the host and configure the device layout.
2. Use the [user guide](docs/Motion_Server_User_Manual_KR.md) and Control Panels
   to check the server and devices.
3. Build your application with the [API manual](docs/motion_server_api_basic.md)
   and the reference clients below. Your application owns sequence execution and
   determines when to advance to the next step using responses and feedback.

For further reading, see the [documentation guide](docs/README.md),
[software architecture](docs/motion_server_architecture.md),
[test procedure](docs/test_procedure.md), [design decisions](docs/decisions.md),
[remaining tasks](docs/remaining_tasks.md), and [work log](docs/worklog.md).

## Reference Clients

RF-002 reference clients are independent from the Axis/IO Control Panel clients:

- Python: `reference_clients/python`
- Node-RED: `reference_clients/node_red/node-red-contrib-motion-server`

Install the Python package from the repository root:

```powershell
python -m pip install -e reference_clients/python
```

Install the Node-RED package from the Node-RED user directory and restart Node-RED:

```powershell
npm install C:\path\to\motion-server\reference_clients\node_red\node-red-contrib-motion-server
```

The Node-RED package provides shared Connection/Connection Control, Request, Feedback and Connection Status
nodes. Import `01_connection_and_authority.json` first for the common server/authority Dashboard, then import
only the required functional flows from its `examples/flows` directory. Motion and output-changing examples
use manual controls and never run automatically on deploy.
The common Dashboard combines endpoint, connection, authority, bus/server recovery controls and the compact
Motion Server status summary in one control-panel-style area.

## Mock path

The mock path uses the same Motion Server TCP API as the real drive path, but
selects the virtual CiA402 servo backend.

```text
Axis/IO Control Panel or reference client
  -> TCP JSON
  -> Motion Server backend=mock
  -> MockMaster / MockSlave
  -> device/virtual_servo_drive
```

## Real Festo CMMT path

The real-drive path runs PySOEM on the PC that is
physically connected to the EtherCAT device.

```text
Axis/IO Control Panel or reference client
  -> TCP JSON
  -> Motion Server on the EtherCAT host PC
  -> Festo CMMT-AS
```

Use the scripts under `scripts/host` and `scripts/windows`
for the current recommended entry points.

## Recommended real-drive startup

Dockerized Ubuntu EtherCAT host PC:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
# Log out and back in after adding the docker group.

bash scripts/host/adapters.sh
bash scripts/host/start.sh
```

`scripts/host/start.sh` starts the existing Motion Server image. Rebuild the
server image only after changing the Motion Server Dockerfile or dependencies:

```bash
bash scripts/host/start.sh --build
```

Runtime settings are stored in `.env`:

```text
PYSOEM_INTERFACE=enp1s0
MOTION_SERVER_BACKEND=pysoem
MOTION_SERVER_BUS=cmmt
MOTION_SERVER_PORT=15000
MOTION_SERVER_HEARTBEAT_PERIOD=0.05
MOTION_SERVER_HEARTBEAT_TIMEOUT=0.2
PYSOEM_CYCLE_TIME=0.01
```

CMMT-specific settings are stored in `device/cmmt/.env`:

```text
MOTION_SERVER_MOTION_MODE=pp
```

On Linux, `.env` is a hidden file. In the Files app, press `Ctrl+H` to show it,
or check it from a terminal:

```bash
ls -la
cat .env
```

The host scripts pass this file explicitly to Docker Compose with
`--env-file .env`. When `scripts/host/start.sh` runs, it prints the backend,
bus layout, and interface values it read from `.env`.

For a three-axis mock backend, use:

```text
MOTION_SERVER_BACKEND=mock
MOTION_SERVER_BUS=cmmt,cmmt,cmmt
```

For multiple same-profile CiA402 slaves, edit `.env` once:

```bash
nano .env
bash scripts/host/start.sh
```

Or use the start helper:

```bash
bash scripts/host/start.sh
docker logs -f motion-server
```

The Dockerized Motion Server uses host networking and privileged raw Ethernet
access so the container can send EtherCAT frames through the Ubuntu PC NIC.
The Motion Server image is intentionally separate from the GUI image. The server
image contains PySOEM and EtherCAT access only; the panel image contains Tk GUI
dependencies and connects to the server through TCP.

Non-motion EtherCAT devices can be listed in the same physical bus layout with
an `io:` prefix. For example, two CMMT motion axes plus a CPX-AP-I-EC I/O
station:

```text
MOTION_SERVER_BUS=cmmt,cmmt,io:cpx_ap_i_ec:io0
```

The CPX profile keeps the device PDO mapping. The station AP module layout is
declared in the common Motion Server configuration:

```text
MOTION_SERVER_IO_io0_MODULES=di:16,do:16,aio:2:1
```

The configured byte size from `MOTION_SERVER_IO_<id>_MODULES` is compared with
the actual PDO byte size before `config_map()`.

`MOTION_SERVER_IO_<io>_IOL_PORTS` accepts `<port>:<iodd_key>` or
`<port>:<iodd_key>:<process_data_profile>`. Omitting the profile selects the first
`ProcessData` element in IODD document order, so existing two-field entries need
no edits. An explicit profile uses the IODD `Condition value` as a non-negative
decimal integer, not an array index or profile name. For example,
`0:Balluff_BCM_R16E_004_CI01:2` selects `P_Vibration_Accel`; `:240` selects
`P_Custom_Profile`. Unknown or ambiguous numbers are rejected. A profile without
a Condition can be selected only by omitting the setting (if it is first).
Existing `iol<ordinal>.<port>` and `<module-slot>.<port>` selectors remain supported
for multiple IO-Link modules, as do `none` entries for unused ports.
The selected profile determines per-port input/output sizes, automatic module
variant sizing and catalog metadata (`process_data_profile` is the numeric value,
or null for an unconditional profile; `process_data_profile_id` is its IODD name). This selects server
metadata only; it does not write an IO-Link device parameter to switch its mode.
The physical device must already use the matching process data profile.

The CPX object dictionary is based on the CPX-AP-I-EC manual. Fixed objects
such as `0x27F0`, `0x27F1`, `0xF000`, and `0xF980` are declared directly.
Repeating module areas such as `0x9000...0x9FFF`, `0xA000...0xA4F0`,
`0xF030...0xF03F`, and `0xF050...0xF05F` are resolved by the CPX object lookup
helper instead of being expanded into thousands of static entries.

During startup/reconnect in PRE-OP, CMMT profiles write the selected PDO mapping and
assignment, then read back and validate it before process-image mapping. CPX uses its
device process image and validates it against the configured modules and index stride.
Mappings are not changed during ordinary cyclic motion. A mismatch leaves the server
in initialization-error state with its TCP service available.

Linux local Motion Server control and visualization:

```bash
bash scripts/host/panel.sh
```

The panel runs in a separate `axis_panel` container, connects directly to the
local Motion Server TCP port from `.env`, and does not require ROS2. It can send
target positions, apply profile velocity/accel/decel limits, send alarm ack,
run two-point repeat motion, and show position/velocity traces. It also
provides manual CiA402 controlword commands after the server's automatic
startup sequence has enabled the drive.

The panel container is intentionally short-lived: closing the GUI exits and
removes the container. The image is not rebuilt every time. Rebuild it only
after changing the panel Dockerfile or dependencies:

```bash
bash scripts/host/panel.sh --build
```

Control panel source code is grouped under `control_panel/`.
`control_panel/axis_control_panel` contains the motion-axis panel, and
`control_panel/io_control_panel` contains the CPX remote I/O monitoring and
digital output control panel. `control_panel/gamepad_control_panel` contains the
DualSense/Gamepad manual motion panel. On Windows, the I/O panel can be started from:

```powershell
.\scripts\windows\io_panel.ps1
```

The Axis panel and Gamepad Control Panel use the same direct Windows launch flow:

```powershell
.\scripts\windows\axis_panel.ps1
.\scripts\windows\gamepad.ps1 -ListDevices
.\scripts\windows\gamepad.ps1
```

The Motion Server accepts multiple TCP clients. Command messages require command
authority on the TCP connection that sends them: a client sends
`authority/acquire` once before motion commands, manual controlwords,
limit changes, mode changes, jogs, or alarm ack. If no client owns authority,
the server grants it to that connection. If another connection already owns it,
the server rejects the request with `authority_busy` and reports the current
owner. Feedback remains broadcast to all connected clients. Closing the owning
connection or sending `authority/release` releases authority.

Motion modes:

```text
pp   Profile Position, default and recommended for Windows/Linux non-RT hosts
pv   Profile Velocity, target velocity command through `axis/move_vel`
csp  Cyclic Synchronous Position, available for smoother target streaming
```

Motion Server command and feedback units are normalized at the TCP API boundary:
linear axes use `mm`, `mm/s`, `mm/s^2`, and rotary axes use `deg`, `deg/s`,
`deg/s^2`. The server reads the drive user unit and conversion settings during
startup and converts to the drive's PDO/SDO units internally.

The Motion Server does not use a manual CSP count scale. For real CMMT drives,
the server reads the drive user unit and converting unit exponents from OD
objects such as `0x216E` and `0x2194`, then calculates the per-axis API-to-drive
scale automatically. For virtual axes, the same values come from the virtual
servo drive profile and config.

For CSP testing, reduce the process-data cycle time in `.env` if the generated
target stream is too coarse:

```text
PYSOEM_CYCLE_TIME=0.002
```

The Motion Server log prints `CSP_CV=...` and `CSP_CP=...` for each axis so the
generated CSP command velocity/position can be compared with the drive's actual
velocity/position. Some drives do not expose CiA402 object `0x60C2`
interpolation time period; the Motion Server treats that as a supported fallback
and continues without writing it.

The server and local panel use the drive's `0x606C` actual velocity feedback.
Virtual axes obtain the same OD defaults and unit metadata from their configured
CMMT device profile as real axes.

The panel needs an active Linux desktop/X11 session. The boot service starts
only the Motion Server container; open the panel manually with
`bash scripts/host/panel.sh` after logging into the desktop.

To start the Dockerized PySOEM server automatically when the Ubuntu PC boots:

```bash
sudo bash scripts/host/service.sh install
systemctl status motion-server.service
docker logs -f motion-server
```

After this installation, Ubuntu boot starts Docker, systemd runs
`motion-server.service`, and the service starts the
`motion-server` container. The container command starts
`motion_server/server.py` automatically.

To change the EtherCAT NIC or axis count later, edit `.env` and restart:

```bash
sudo systemctl restart motion-server.service
```

For a multi-axis boot service:

```bash
nano .env
sudo systemctl restart motion-server.service
```

To remove the boot service:

```bash
sudo bash scripts/host/service.sh uninstall
```

If the boot service fails, check the systemd and container logs:

```bash
systemctl status motion-server.service --no-pager
journalctl -xeu motion-server.service --no-pager
docker ps -a
docker logs motion-server
```

If an old container name is blocking startup:

```bash
docker rm -f motion-server
sudo systemctl restart motion-server.service
```

If Docker cannot resolve Docker Hub, configure Docker DNS and restart Docker:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
EOF
sudo systemctl restart docker
docker pull ubuntu:24.04
```

Windows PowerShell, only when the EtherCAT device is connected to Windows:

```powershell
.\scripts\windows\motion_server.ps1
```

## Update the Ubuntu EtherCAT host

The Linux checkout is maintained directly from GitHub. Clone it once:

```bash
cd /home/festo/Documents
git clone https://github.com/IlgonKo/motion-server.git motion-server
```

Update an existing checkout with a fast-forward pull:

```bash
cd /home/festo/Documents/motion-server
git pull --ff-only
```

Runtime `.env` files remain local to the Linux host and are not tracked by Git.

## Folder guide

```text
motion_server/         Motion Server TCP API, backend selection, local panel, and host entrypoint
control_panel/         Axis, I/O, and Gamepad Control Panels
control_panel/common/protocol/ Shared response decoding and Heartbeat helpers for Axis/I/O Panels
diagnostics/         Adapter listing, PDO dump, and smoke-test utilities
docker/motion_server/  Motion Server Dockerfile and compose file
docker/axis_panel/   Axis Control Panel Dockerfile
scripts/host/        Ubuntu EtherCAT host commands: start, stop, panel, service, adapters
scripts/windows/     Windows sync helper and optional direct Motion Server launcher
ethercat/            Mock/PySOEM EtherCAT transport, distributed clock, and WKC code
device/pdo_metadata/ PDO mapping entry and data type metadata helpers
device/cia402/       Common CiA402 state machine
device/cmmt/         Festo CMMT profile, vendor OD extensions, PDO codec, and settings
device/cpx_ap_i_ec/  Festo CPX-AP-I-EC I/O profile, PDO codec, and settings
device/virtual_servo_drive/ Virtual servo-drive model, OD model, and OD/PDO bridge
```

## Regression and release checks

```bash
python -m pip install -r requirements.txt
python -B -m scripts.check_api_docs
python -B -m scripts.run_tests --profile unit --report reports/unit.json
python -B -m scripts.run_tests --profile integration --report reports/integration.json
```

Linux headless GUI checks require Tk and `xvfb-run -a`. Hardware checks are explicit and separate;
Node-RED tests are excluded until requested. See [deployment validation](docs/deployment_validation.md),
[installation manual](docs/Motion_Server_Installation_Manual_Basic_Mode.md), and
[user manual](docs/Motion_Server_User_Manual_KR.md). Old Rev. 1.0 Word manuals are historical, not current instructions.
