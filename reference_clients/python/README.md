# Motion Server Python Reference Client

This package provides the minimal reusable transport boundary for the Motion Server TCP JSON-lines API.
It intentionally does not wrap individual Motion Server commands as Python methods.

## Install

```powershell
python -m pip install -e reference_clients/python
```

## Use

API numeric fields must be Python `int`/`float` values, not numeric strings or Boolean values.
For example use `{"cmd": "system/axis/param_read", "axis": 0, "index": 0x6041, "subindex": 0}`.
Python hexadecimal integer literals serialize as JSON numbers. The transport does not coerce fields or
validate response schemas; text and hexadecimal byte payload fields remain strings.

```python
from motion_server_reference_client import MotionServerClient

client = MotionServerClient("127.0.0.1", 15000)
client.start()
if not client.wait_connected(timeout=5.0):
    raise RuntimeError(client.last_error)

response = client.request({"cmd": "system/server/status"})
feedback = client.get_feedback(timeout=1.0)
client.stop()
```

`request()` returns the raw Motion Server Success or Fail envelope. A server Fail response is not converted
to a Python exception. Client connection, timeout and usage failures use the exceptions exported by this
package.

The client reconnects every second. Requests that were pending when the connection was lost fail and are
never retransmitted. Command authority is connection-owned and is never reacquired automatically.

## AI reference program

[Pick & Place](examples/pick_place/README.md) demonstrates direct API composition, shared CLI/Tkinter
execution and optional Teaching. It is source-only example code, not an additional client API layer.
Read and adapt its configuration before explicitly running motion; defaults are illustrative, not safe hardware presets.
