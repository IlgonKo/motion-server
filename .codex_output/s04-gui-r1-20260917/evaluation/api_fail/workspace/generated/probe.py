import json
from pathlib import Path
from motion_server_reference_client import MotionServerClient
c = MotionServerClient('127.0.0.1', 52728)
c.start()
try:
    assert c.wait_connected(5), c.last_error
    data = {}
    for cmd in ('system/server/status', 'system/axes/status'):
        data[cmd] = c.request({'cmd': cmd}, timeout=5)
    data['feedback'] = c.get_feedback(timeout=2)
    Path('generated/probe.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(data['system/axes/status']['data']['axis_metadata'], indent=2))
finally:
    c.stop()
