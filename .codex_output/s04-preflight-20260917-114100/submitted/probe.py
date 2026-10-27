import json
from pathlib import Path
import platform
import socket


print(f"Python version: {platform.python_version()}", flush=True)
print(f"6*7 = {6 * 7}", flush=True)
input_path = Path(__file__).resolve().parent.parent / "input.txt"
with input_path.open("r", encoding="utf-8", newline="") as source:
    input_text = source.read()
print(f"input.txt: {input_text!r}", flush=True)

request = {"cmd": "system/server/status", "request_id": "preflight-42"}
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
    connection.settimeout(5)
    connection.connect(("127.0.0.1", 59994))
    connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
    with connection.makefile("r", encoding="utf-8") as messages:
        for line in messages:
            response = json.loads(line)
            if response.get("request_id") != request["request_id"]:
                continue
            print(f"Response: {json.dumps(response)}", flush=True)
            assert response.get("result") == "success", response
            assert response.get("data", {}).get("initialized") is True, response
            break
        else:
            raise RuntimeError("Connection closed before preflight response arrived")

print("PREFLIGHT_OK", flush=True)
