"""Independent CLI preflight only; no sequence generation or hardware access."""
import hashlib
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_ai_pick_place_tcp import PickPlaceTcpTests, success

report = ROOT / '.codex_output' / ('s04-preflight-' + time.strftime('%Y%m%d-%H%M%S'))
report.mkdir(exist_ok=False)
workspace = Path(tempfile.mkdtemp(prefix='s04-preflight-'))
# Explicit evaluator access must survive a different owner on agent-created files.
# Only this newly created workspace is changed; no recursive reset or broad grant.
identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
sid = next(csv.reader(io.StringIO(identity)))[1]
if not sid.startswith('S-1-'):
    raise ValueError('Invalid evaluator SID')
before_acl = subprocess.check_output(['icacls', str(workspace)], text=True)
grant = subprocess.run(['icacls', str(workspace), '/grant', f'*{sid}:(OI)(CI)(RX)'],
                       capture_output=True, text=True, check=True)
(report/'workspace-acl-before.txt').write_text(before_acl, encoding='utf-8')
(report/'workspace-acl-grant.txt').write_text(grant.stdout, encoding='utf-8')
(workspace / 'generated').mkdir()
(workspace / 'input.txt').write_text('motion-server-preflight-42\n', encoding='utf-8')
fixture = PickPlaceTcpTests('test_normal_actual_tcp_and_mock_motion')
fixture.setUp()
result = {'workspace': str(workspace), 'report': str(report), 'port': fixture.port,
          'mock_pid': fixture.process.pid, 'checks': {}, 'collection_errors': [],
          'evaluator_sid': sid, 'added_permission': '(OI)(CI)(RX)'}
print(json.dumps(result), flush=True)
try:
    success(fixture.client.request({'cmd': 'system/authority/release'}))
    prompt = f'''This is a permission/environment preflight, NOT sequence generation.
Work only in this workspace. Do not change permissions, install packages, use other servers, or request elevated/full-access execution.
1. Read input.txt and report its exact content.
2. Use apply_patch to create generated/probe.py. It must print Python version and 6*7, read input.txt, connect by socket ONLY to 127.0.0.1:{fixture.port}, send one newline-delimited JSON request {{"cmd":"system/server/status","request_id":"preflight-42"}}, read newline-delimited messages until that response arrives, assert result success and data.initialized true, and print PREFLIGHT_OK. Use socket timeout 5 seconds. No control/motion/I/O write commands.
3. Execute it using PowerShell &: {sys.executable} -B generated/probe.py. Do not merely print the command.
4. Create generated/summary.md with actual results and generated/nested/note.txt with the input text, using apply_patch. Report SHA256 of these three files using Get-FileHash. If a step fails, report failure without changing ACLs, installing tools, or bypassing the sandbox.
Stop after these checks. No retries with relaxed permissions and no motion program generation.'''
    (workspace / 'prompt.txt').write_text(prompt, encoding='utf-8')
    (report / 'prompt.txt').write_text(prompt, encoding='utf-8')
    command = [shutil.which('codex'), 'exec', '--ignore-user-config', '--skip-git-repo-check',
               '--sandbox', 'workspace-write', '-c', 'windows.sandbox="elevated"',
               '-c', 'sandbox_workspace_write.network_access=true', '--json',
               '-o', str(report / 'final.txt'), '-']
    result['command'] = command
    result['cli_version'] = subprocess.check_output([command[0], '--version'], text=True).strip()
    with (report / 'events.jsonl').open('w', encoding='utf-8') as out, (report / 'stderr.txt').open('w', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE,
                                   stdout=out, stderr=err, text=True, encoding='utf-8')
        result['cli_pid'] = process.pid
        (report / 'environment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        process.communicate(prompt)  # No arbitrary generation deadline.
        result['cli_exit'] = process.returncode
    result['checks']['server_alive_after_agent'] = fixture.process.poll() is None
    result['checks']['server_status_after_agent'] = success(fixture.client.request({'cmd':'system/server/status'}))['initialized']
    hashes = {}
    for relative in ('probe.py', 'summary.md', 'nested/note.txt'):
        try:
            source = workspace / 'generated' / relative
            payload = source.read_bytes()
            target = report / 'submitted' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            hashes[relative] = hashlib.sha256(payload).hexdigest()
            assert target.read_bytes() == payload
        except Exception as exc:
            result['collection_errors'].append({'file':relative, 'error':repr(exc)})
    result['sha256'] = hashes
    acl = subprocess.run(['icacls', str(workspace/'generated'), '/T'], capture_output=True, text=True)
    (report/'generated-acl.txt').write_text(acl.stdout + acl.stderr, encoding='utf-8')
    result['checks']['parent_read_and_copy'] = len(hashes) == 3 and not result['collection_errors']
    result['checks']['server_alive_after_collection'] = fixture.process.poll() is None
    result['checks']['server_status_after_collection'] = success(fixture.client.request({'cmd':'system/server/status'}))['initialized']
    if result['checks']['parent_read_and_copy']:
        shutil.copy2(workspace/'input.txt', report/'input.txt')
        check = subprocess.run([sys.executable, '-B', str(report/'submitted/probe.py')], cwd=workspace,
                               capture_output=True, text=True, timeout=20)
        (report/'parent-probe-stdout.txt').write_text(check.stdout, encoding='utf-8')
        (report/'parent-probe-stderr.txt').write_text(check.stderr, encoding='utf-8')
        result['checks']['parent_execution'] = check.returncode == 0 and 'PREFLIGHT_OK' in check.stdout
    else:
        result['checks']['parent_execution'] = False
except Exception as exc:
    result['error'] = repr(exc)
finally:
    # Deliberate cleanup only after agent exit and collection checks, not on collection failure.
    fixture.log.flush()
    shutil.copy2(fixture.folder/'server.log', report/'server.log')
    result['cleanup_reason'] = 'Preflight ended; stop only its owned Mock fixture'
    fixture.cleanup()
    result['checks']['owned_mock_stopped'] = fixture.process.poll() is not None
    (report/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
