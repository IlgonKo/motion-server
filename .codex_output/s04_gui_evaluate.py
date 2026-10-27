"""Independent GUI callbacks + actual Tk event loop + isolated Mock TCP; no generated edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_ai_pick_place_tcp import PickPlaceTcpTests, success
from motion_server.api.schema_loader import api_contracts
from s04_observer import Observer

parser = argparse.ArgumentParser()
parser.add_argument('run_id')
parser.add_argument('--case')
parser.add_argument('--result-name')
parser.add_argument('--evaluation-dir', default='evaluation')
args = parser.parse_args()
report = ROOT/'.codex_output'/args.run_id
cases = ['normal', 'stop', 'close', 'input_timeout', 'api_fail', 'fault',
         'connection_loss', 'authority_loss', 'response_timeout']
if not args.case:
    results = []
    for case in cases:
        folder = report/args.evaluation_dir/case
        folder.mkdir(parents=True, exist_ok=False)
        with (folder/'stdout.txt').open('w', encoding='utf-8') as out, (folder/'stderr.txt').open('w', encoding='utf-8') as err:
            process = subprocess.run([sys.executable, '-B', __file__, args.run_id, '--case', case,
                                      '--evaluation-dir', args.evaluation_dir],
                                     stdout=out, stderr=err)
        result_path = folder/'result.json'
        result = json.loads(result_path.read_text()) if result_path.exists() else {'case':case, 'harness_error':'no result', 'passed':False}
        results.append(result)
        (report/(args.evaluation_dir+'-results.json')).write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    sys.exit(0 if all(r['passed'] for r in results) else 1)

case = args.case
folder = report/args.evaluation_dir/(args.result_name or case)
folder.mkdir(parents=True, exist_ok=True)
source = Path(json.loads((report/'environment.json').read_text())['workspace'])
workspace = folder/'workspace'
shutil.copytree(source, workspace, ignore=shutil.ignore_patterns('generated', '__pycache__', '*.pyc'))
shutil.copytree(report/'submitted', workspace/'generated')
original = {str(p.relative_to(workspace/'generated')):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (workspace/'generated').rglob('*.py')}
sys.path.insert(0, str(workspace))
from generated.gui import Panel

fixture = PickPlaceTcpTests('test_normal_actual_tcp_and_mock_motion')
fixture.inject_wkc = case == 'fault'
fixture.setUp()
root = panel = proxy = None
checks = {}
started = time.monotonic()
gui_errors = []
result = {'case':case, 'passed':False,
          'model_tokens':{'additional_model_calls':0,'input_tokens':0,'output_tokens':0,
                          'note':'Generation usage recorded separately; evaluator conversation excluded'}}

def pump(predicate, timeout=40):
    until = time.monotonic()+timeout
    while time.monotonic() < until:
        if panel.closed:
            if predicate(): return
            raise AssertionError('Window closed before condition')
        root.update()
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('GUI condition timeout: '+str(panel.phase.get()))

def moves():
    return [m for m in proxy.requests() if m['cmd']=='system/axes/move_abs']

def outputs():
    return [m for m in proxy.requests() if m['cmd']=='system/io/output_write']

def complete(f, positions):
    return bool(f and f.get('process_data_valid') and all(
        abs(f['actual_positions'][i]-p)<=.5 and f['statuswords'][i]&1024
        and not f['statuswords'][i]&256 for i,p in enumerate(positions)))

try:
    proxy = Observer(fixture.port, 'system/axes/move_abs' if case=='response_timeout' else None)
    config_path = workspace/'generated/sequence.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config.update(host='127.0.0.1', port=proxy.port)
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    shutil.copy2(fixture.folder/'.env', workspace/'config.txt')
    if case == 'api_fail':
        success(fixture.client.request({'cmd':'system/axis/disable','axis':1}))
        fixture.wait_for(lambda f:f['statuswords'][1]&0x6f != 0x27)
    if case == 'response_timeout': fixture.set_inputs()
    success(fixture.client.request({'cmd':'system/authority/release'}))
    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda *exc: gui_errors.append(''.join(traceback.format_exception(*exc)))
    panel = Panel(root, config_path)
    panel.buttons['Connect'].invoke()
    pump(lambda:not panel.busy and panel.metadata_ok)
    pump(lambda:str(panel.buttons['Request authority']['state'])=='normal')
    panel.buttons['Request authority'].invoke()
    pump(lambda:not panel.busy and str(panel.buttons['Run']['state'])=='normal')
    ticks = []
    tick_timer = [None]
    def tick():
        ticks.append(time.monotonic())
        if not panel.closed: tick_timer[0] = root.after(20,tick)
    tick_timer[0] = root.after(20,tick)
    destroy = root.destroy
    def destroy_with_observer_cleanup():
        # Cancel only the evaluator's heartbeat, not any generated GUI callback.
        if tick_timer[0] is not None:
            root.after_cancel(tick_timer[0])
        destroy()
    root.destroy = destroy_with_observer_cleanup
    panel.buttons['Run'].invoke()
    first_sequence = panel.sequence
    panel.run()  # direct duplicate callback, even before next widget-state refresh
    checks['duplicate_run_ignored'] = panel.sequence is first_sequence
    if case not in ('api_fail','response_timeout'):
        pump(lambda:len(outputs())>=2 or not panel.busy)
        checks['reached_input_wait'] = len(outputs())==2 and panel.busy
        if case=='normal':
            input_at = time.monotonic()
            fixture.set_inputs()
        elif case=='stop':
            panel.buttons['Stop'].invoke()
        elif case=='close':
            close_callback = root.protocol('WM_DELETE_WINDOW')
            root.tk.call(close_callback)
        elif case=='fault':
            (fixture.folder/'inject-wkc').touch()
        elif case=='connection_loss':
            proxy.disconnect.set()
        elif case=='authority_loss':
            success(panel.client.request({'cmd':'system/authority/release'}))
    if case=='close':
        pump(lambda:panel.closed, 40)
    else:
        pump(lambda:not panel.busy, 45)
        if case=='api_fail':
            # Immediate API rejection may finish within one tick. Observe a fixed extra
            # event-loop interval instead of confusing fast completion with GUI blocking.
            until=time.monotonic()+.35
            pump(lambda:time.monotonic()>=until, 2)
    final = fixture.feedback.snapshot()[2]
    state = panel.sequence.state
    checks['state'] = state==('completed' if case=='normal' else 'cancelled' if case in ('stop','close') else 'failed')
    checks['gui_responsive'] = len(ticks)>2 and max((b-a for a,b in zip(ticks,ticks[1:])),default=0)<.75
    if case!='close':
        (folder/'gui-state.json').write_text(json.dumps({'status':panel.status.get(),'phase':panel.phase.get(),
            'error':panel.error.get(),'history':panel.history},indent=2),encoding='utf-8')
    requests = proxy.requests()
    count_before_close = len(requests)
    if case=='normal':
        checks['authority_retained_after_run'] = bool(panel.feedback.snapshot()[2]['command_authority']['owned_by_this_client'])
        checks['two_moves'] = len(moves())==2
        checks['final_position'] = complete(final,[100,110,120])
        checks['output_sequence'] = [(m.get('slot'),m.get('kind'),m.get('channel'),m.get('value')) for m in outputs()]==[
            (1,'digital',0,True),(2,'analog',0,100),(1,'digital',0,False),(2,'analog',0,0)]
        second = [r for r in proxy.records if r['direction']=='request' and r['data']['cmd']=='system/axes/move_abs'][1:]
        checks['input_gate'] = bool(second and second[0]['time']>=input_at)
    else:
        checks['no_place_or_replay'] = len(moves())==1
        checks['no_release_outputs'] = len(outputs())==(0 if case in ('api_fail','response_timeout') else 2)
    if case=='response_timeout':
        pump(lambda:proxy.delivered.is_set(), 8)
        until=time.monotonic()+.4
        pump(lambda:time.monotonic()>=until,2)
        checks['late_success_does_not_resume'] = panel.sequence.state=='failed' and len(moves())==1
    if case!='close':
        panel.close()
        pump(lambda:panel.closed, 40)
    requests=proxy.requests()
    checks['pick_request'] = bool(moves() and moves()[0].get('axes')==[0,1,2] and moves()[0].get('positions')==[50,60,70])
    checks['velocities'] = all(m.get('profile_velocities')==([50,50,40] if i==0 else [50,50,20]) for i,m in enumerate(moves()))
    profiles=[m for m in requests if m['cmd']=='system/axis/profile']
    checks['common_profile_once'] = len(profiles)==3 and all(m.get('profile_acceleration')==100 and m.get('profile_deceleration')==100 for m in profiles)
    checks['no_auto_recovery'] = not any(m['cmd'].endswith(('/enable','/disable','/home','/restart','/reconnect','/fault_reset')) for m in requests)
    checks['no_authority_reacquire'] = sum(m['cmd']=='system/authority/request' for m in requests)==1
    schema_errors=[]
    for m in requests:
        clean={k:v for k,v in m.items() if k!='request_id'}
        schema_errors.extend(str(e) for e in api_contracts().request_errors(clean['cmd'],clean))
    checks['request_schema'] = not schema_errors
    if case not in ('connection_loss','authority_loss','fault'):
        cmds=[m['cmd'] for m in requests]
        checks['stop_then_release'] = 'system/axes/stop' in cmds and 'system/authority/release' in cmds and cmds.index('system/axes/stop')<cmds.index('system/authority/release')
    latest=None
    number=0
    boundaries=True
    for record in proxy.records:
        value=record['data']
        if record['direction']=='server' and value.get('type')=='system/feedback': latest=value
        if record['direction']=='request' and value['cmd']=='system/io/output_write':
            boundaries = boundaries and complete(latest, [50,60,70] if number<2 else [100,110,120])
            number+=1
    checks['completion_before_outputs'] = boundaries
    checks['no_tk_callback_errors'] = not gui_errors
    checks['generated_python_unchanged'] = all(hashlib.sha256((workspace/'generated'/name).read_bytes()).hexdigest()==digest for name,digest in original.items())
    result.update(state=state, schema_errors=schema_errors, gui_errors=gui_errors, max_tick_gap=max((b-a for a,b in zip(ticks,ticks[1:])),default=0),
                  cleanup_confirmed=panel.sequence.cleanup_confirmed)
except Exception as exc:
    result['assessment_error']=repr(exc)
    (folder/'assessment-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
finally:
    if panel and not panel.closed:
        try:
            panel.close()
            pump(lambda:panel.closed,40)
        except Exception as exc: result['cleanup_error']=repr(exc)
    if proxy:
        proxy.close()
        (folder/'trace.json').write_text(json.dumps(proxy.records),encoding='utf-8')
    (folder/'final-feedback.json').write_text(json.dumps(fixture.feedback.snapshot()[2],indent=2),encoding='utf-8')
    fixture.log.flush()
    shutil.copy2(fixture.folder/'server.log',folder/'server.log')
    fixture.cleanup()
    result.update(checks=checks, duration=time.monotonic()-started,
                  passed=bool(checks) and all(checks.values()) and 'assessment_error' not in result and 'cleanup_error' not in result)
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
sys.exit(0 if result['passed'] else 1)
