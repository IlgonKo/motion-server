import sys, json
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference_clients/python'))
from motion_server_reference_client import MotionServerClient
c = MotionServerClient('127.0.0.1', 62554)
c.start()
try:
    if not c.wait_connected(timeout=5): raise RuntimeError(c.last_error)
    result = c.request({'cmd':'system/axes/status'}, timeout=5)
    Path(__file__).with_name('metadata.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    f = c.get_feedback(timeout=2)
    Path(__file__).with_name('initial_feedback.json').write_text(json.dumps(f, indent=2), encoding='utf-8')
finally:
    c.stop()
