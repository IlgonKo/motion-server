import hashlib
import csv
import io
import json
import shutil
import sys
import tempfile
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_ai_pick_place_tcp import PickPlaceTcpTests, success

run_id = sys.argv[1] if len(sys.argv) > 1 else 's04-basic-r1'
gui = '--gui' in sys.argv[2:]
if not run_id.replace('-', '').isalnum():
    raise ValueError('Invalid run id')
report = ROOT/'.codex_output'/run_id
report.mkdir(exist_ok=False)
fixture = PickPlaceTcpTests('test_normal_actual_tcp_and_mock_motion')
fixture.setUp()
try:
    workspace = Path(tempfile.mkdtemp(prefix=run_id+'-'))
    identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
    evaluator_sid = next(csv.reader(io.StringIO(identity)))[1]
    if not evaluator_sid.startswith('S-1-'):
        raise ValueError('Invalid evaluator SID')
    # Restrict the grant to this fresh workspace, inherited by future generated files.
    grant = subprocess.run(['icacls', str(workspace), '/grant', f'*{evaluator_sid}:(OI)(CI)(RX)'],
                           capture_output=True, text=True, check=True)
    (report/'workspace-acl-grant.txt').write_text(grant.stdout, encoding='utf-8')
    (workspace/'generated').mkdir()
    sources = []
    for base in ('docs/ai', 'reference_clients/python', 'motion_server/api/schema', 'configuration'):
        sources += [p for p in (ROOT/base).rglob('*') if p.is_file()
                    and p.suffix in {'.py', '.md', '.json', '.toml'} and '__pycache__' not in p.parts]
    sources += [ROOT/'docs/motion_server_api_basic.md', ROOT/'control_panel/axis_control_panel/statusword.py']
    for source in sources:
        dest = workspace/source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    shutil.copy2(fixture.folder/'.env', workspace/'config.txt')
    text = (ROOT/'docs/ai/prompts/motion_io_sequence.md').read_text(encoding='utf-8').split('```text')[1].split('```')[0]
    text = text.replace('127.0.0.1:15000', f'127.0.0.1:{fixture.port}')
    text = text.replace('첨부/지정된 파일 사용', '작업 폴더의 config.txt 사용 (Mock 시험 서버의 실제 적용 설정)')
    if gui:
        manual = json.loads((ROOT/'.codex_output/manual-sequence-test/generated/settings.json').read_text(encoding='utf-8'))
        for name, old in [('pick', 'X=10.0, Y=20.0, Z=5.0'), ('place', 'X=30.0, Y=40.0, Z=5.0')]:
            positions = manual[name]['positions']
            speeds = manual[name]['profile_velocities']
            text = text.replace(old + '; 속도 X/Y/Z=5.0/5.0/2.0.',
                ', '.join(f'{role}={value}' for role, value in zip('XYZ', positions)) +
                '; 속도 X/Y/Z=' + '/'.join(str(v) for v in speeds) + '.')
        text = text.replace('- GUI: 아니오', '- GUI: 예')
        text += '\n' + (ROOT/'docs/ai/prompts/sequence_gui.md').read_text(encoding='utf-8').split('```text')[1].split('```')[0]
        (report/'manual-settings-reference.json').write_text(json.dumps(manual, indent=2), encoding='utf-8')
    else:
        text = text.replace('X=10.0, Y=20.0, Z=5.0', 'X=0.5, Y=0.6, Z=0.7')
        text = text.replace('X=30.0, Y=40.0, Z=5.0', 'X=1.0, Y=1.1, Z=1.2')
    text += '\n작업 조건: 산출물은 generated/에 작성. 제공 자료는 읽기 전용이며 변경하지 마.\n'
    text += '이 폴더 밖의 파일, 다른 대화, 외부 검색, 평가 도구/서버 구현은 사용하지 마. RF 평가계획 링크는 제공 제외 자료다.\n'
    text += '이 주소의 Mock 서버만 사용 가능하며 이미 정상 초기화/Enable/Homing 완료다. DI/AI 시험 입력도 준비되어 있다.\n'
    text += '한 번 실행할 수 있는 CLI 진입점과 실행 방법, 자체 테스트를 제공해.\n'
    if gui:
        text += 'GUI 진입점도 제공하고 Run/Stop/종료 테스트를 수행해. Teaching은 선택하지 않았어. 시험 GUI는 사용자 조작을 기다리며 무기한 남겨 두지 마.\n'
    text += 'Python 실행 경로: C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe (PowerShell에서는 & 연산자 사용).\n'
    (workspace/'prompt.txt').write_text(text, encoding='utf-8')
    manifest = {str(p.relative_to(workspace)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in workspace.rglob('*') if p.is_file()}
    fixture.set_inputs()
    success(fixture.client.request({'cmd':'system/authority/release'}))
    (report/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (report/'environment.json').write_text(json.dumps({'workspace':str(workspace),'port':fixture.port,
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'generation_time_limit':None,
        'isolation':'fresh CLI session, workspace-write; supplied-file boundary audited, not a VM',
        'scenario':('GUI pick/place, no Teaching, first generation' if gui else 'basic pick/place, no GUI, no Teaching, first generation')},indent=2),encoding='utf-8')
    shutil.copy2(workspace/'prompt.txt',report/'prompt.txt')
    print(json.dumps({'workspace':str(workspace),'port':fixture.port}),flush=True)
    previous = {}
    revision = 0
    while not (report/'stop').exists():
        generated = workspace/'generated'
        try:
            current = {str(p.relative_to(generated)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in generated.rglob('*') if p.is_file() and p.suffix in {'.py','.json','.md'}
                       and '__pycache__' not in p.parts} if generated.exists() else {}
            if current and current != previous:
                revision += 1
                shutil.copytree(generated,report/'snapshots'/f'{revision:03d}',
                                ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                previous = current
        except OSError as exc:
            # Preserve failed collection evidence without ending the agent's Mock session.
            with (report/'collection-errors.jsonl').open('a',encoding='utf-8') as errors:
                errors.write(json.dumps({'time':time.time(),'revision':revision,'error':repr(exc)})+'\n')
        time.sleep(.2)
finally:
    fixture.log.flush()
    if 'report' in globals():
        shutil.copy2(fixture.folder/'server.log',report/'generation-server.log')
    fixture.cleanup()
