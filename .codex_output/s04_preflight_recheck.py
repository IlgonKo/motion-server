import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_ai_pick_place_tcp import PickPlaceTcpTests
from s04_observer import Observer

report = ROOT/'.codex_output/s04-preflight-20260917-114100'
prior = json.loads((report/'result.json').read_text())
shutil.copy2(Path(prior['workspace'])/'input.txt', report/'input.txt')
fixture = PickPlaceTcpTests('test_normal_actual_tcp_and_mock_motion')
fixture.setUp()
proxy = None
result = {}
try:
    proxy = Observer(fixture.port, listen_port=prior['port'])
    check = subprocess.run([sys.executable, '-B', str(report/'submitted/probe.py')],
                           cwd=report, capture_output=True, text=True, timeout=20)
    result = {'exit_code':check.returncode, 'stdout':check.stdout, 'stderr':check.stderr,
              'passed':check.returncode==0 and 'PREFLIGHT_OK' in check.stdout,
              'change':'Copied original input.txt; generated code unchanged; fresh Mock via same-port proxy'}
finally:
    if proxy:
        proxy.close()
    fixture.cleanup()
    (report/'parent-recheck.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
