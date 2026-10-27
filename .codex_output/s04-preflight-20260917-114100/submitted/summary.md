# Preflight results

- Exact input.txt content (JSON string): "motion-server-preflight-42\r\n".
- Created generated/probe.py using apply_patch.
- Executed with PowerShell &: `& 'C:\Users\Festo\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B generated/probe.py`.
- Process exit code: 0.
- Python version: 3.14.3.
- 6*7 = 42.
- Probe read input.txt and printed its exact content representation.
- Socket destination: 127.0.0.1:59994; timeout: 5 seconds.
- Sent one newline-delimited JSON request: {"cmd":"system/server/status","request_id":"preflight-42"}.
- Matching response: result "success", data.initialized true.
- Both response assertions passed; probe printed PREFLIGHT_OK.
- Created generated/nested/note.txt using apply_patch with the input text. apply_patch normalized its final line ending to LF; the source ends in CRLF, so the note is text-equivalent but not byte-identical.
- Auxiliary inspection failure: System.Text.Json.JsonSerializer.Serialize could not resolve a one-argument overload in PowerShell (exit code 1). ConvertTo-Json subsequently confirmed the exact input content successfully.
- No permissions changed, packages installed, elevated execution requested, other servers contacted, or control/motion/I/O write commands sent.

Actual server response:

```json
{"type": "system/server/status", "result": "success", "data": {"server_mode": "basic", "initialized": true, "runtime_state": "normal", "initialization_failure": null, "cycle_time": 0.008, "feedback_type": "system/feedback", "diagnostic_status": {"level": "normal", "statuses": []}}, "request_id": "preflight-42"}
```
