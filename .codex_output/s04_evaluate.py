"""Black-box generated CLI assessment against isolated real Mock servers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.test_ai_pick_place_tcp import PickPlaceTcpTests, success
from motion_server.api.schema_loader import api_contracts
from s04_observer import Observer

parser=argparse.ArgumentParser()
parser.add_argument('run_id')
parser.add_argument('--entry',required=True)
parser.add_argument('--config',required=True)
parser.add_argument('--config-flag',default='--config')
parser.add_argument('--extra',default='')
parser.add_argument('--artifact-dir',default='submitted')
parser.add_argument('--cases',default='normal,input_timeout,api_fail,stop,fault,connection_loss,authority_loss,response_timeout')
args=parser.parse_args()
report=ROOT/'.codex_output'/args.run_id
source=Path(json.loads((report/'environment.json').read_text())['workspace'])
results=[]

def io_output(feedback,slot,kind):
    for device in feedback.get('io',{}).get('devices',[]):
        if device.get('id')=='io0':
            for module in device.get('modules',[]):
                if module['slot']==slot:
                    return module.get('outputs',{}).get(kind,[None])[0]

def motion_complete(f,positions):
    return bool(f and f.get('process_data_valid') and all(
        abs(f['actual_positions'][i]-p)<=.5 and abs(f['target_positions'][i]-p)<=.5
        and f['statuswords'][i]&1024 and not f['statuswords'][i]&256
        for i,p in enumerate(positions)))

for case in args.cases.split(','):
    case_dir=report/'evaluation'/case
    case_dir.mkdir(parents=True,exist_ok=False)
    fixture=PickPlaceTcpTests('test_normal_actual_tcp_and_mock_motion')
    fixture.inject_wkc = case=='fault'
    fixture.setUp()
    proxy=process=None
    try:
        copied=case_dir/'workspace'
        shutil.copytree(source,copied,ignore=shutil.ignore_patterns('__pycache__','*.pyc','generated'))
        shutil.copytree(report/args.artifact_dir,copied/'generated')
        # Configuration is a deployment input; generated Python is never edited.
        config_path=copied/args.config
        config=json.loads(config_path.read_text(encoding='utf-8'))
        proxy=Observer(fixture.port,'system/axes/move_abs' if case=='response_timeout' else None,
                       listen_port=config['port'])
        config['host']='127.0.0.1'
        config['port']=proxy.port
        config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
        shutil.copy2(fixture.folder/'.env',copied/'config.txt')
        if case=='api_fail':
            success(fixture.client.request({'cmd':'system/axis/disable','axis':1}))
            fixture.wait_for(lambda f: f['statuswords'][1]&0x6f != 0x27)
        if case=='response_timeout':
            fixture.set_inputs()
        success(fixture.client.request({'cmd':'system/authority/release'}))
        marker=case_dir/'interrupt'
        command=[sys.executable,str(ROOT/'.codex_output/s04_sigint_runner.py'),str(marker),
                 str(copied/args.entry)]
        if args.config_flag:
            command += [args.config_flag,str(config_path)]
        command += args.extra.split()
        env={k:v for k,v in os.environ.items() if not k.startswith(('MOTION_SERVER_','PYSOEM_','MOCK_','AXIS_'))}
        env['PYTHONPATH']=str(copied/'reference_clients/python')
        with (case_dir/'stdout.txt').open('w',encoding='utf-8') as out, (case_dir/'stderr.txt').open('w',encoding='utf-8') as err:
            process=subprocess.Popen(command,cwd=copied,env=env,stdout=out,stderr=err)
            started=time.monotonic()
            trigger=None
            changed=False
            input_time=None
            emergency_timeout=False
            while process.poll() is None:
                requests=proxy.requests()
                outputs=[m for m in requests if m['cmd']=='system/io/output_write']
                if len(outputs)>=2 and trigger is None:
                    trigger=time.monotonic()
                if trigger is not None and not changed and time.monotonic()-trigger>=.75:
                    changed=True
                    if case=='normal':
                        input_time=time.monotonic()
                        fixture.set_inputs()
                    elif case=='stop':
                        marker.touch()
                    elif case=='fault':
                        (fixture.folder/'inject-wkc').touch()
                    elif case=='connection_loss':
                        proxy.disconnect.set()
                    elif case=='authority_loss':
                        marker.with_suffix('.authority').touch()
                # Bounded application test, not a generation budget. Requested step timeout is 30s.
                if time.monotonic()-started>65:
                    emergency_timeout=True
                    process.terminate()
                    break
                time.sleep(.02)
            process.wait(timeout=10)
        final=fixture.feedback.snapshot()[2]
        proxy.close()
        requests=proxy.requests()
        moves=[m for m in requests if m['cmd']=='system/axes/move_abs']
        outputs=[m for m in requests if m['cmd']=='system/io/output_write']
        checks={}
        checks['bounded_exit']=not emergency_timeout
        checks['observer_healthy']=proxy.error is None
        errors=[]
        for request in requests:
            data={k:v for k,v in request.items() if k!='request_id'}
            try:
                errors.extend(str(e) for e in api_contracts().request_errors(data['cmd'],data))
            except Exception as exc:
                errors.append(repr(exc))
        checks['request_schema']=not errors
        checks['no_auto_enable_home_disable_recovery']=not any(
            m['cmd'].endswith(('/enable','/disable','/home','/fault_reset','/reconnect','/restart')) for m in requests)
        checks['authority_not_reacquired']=sum(m['cmd']=='system/authority/request' for m in requests)==1
        profiles=[m for m in requests if m['cmd']=='system/axis/profile']
        checks['common_profile_once']=len(profiles)==3 and all(
            m.get('profile_acceleration')==100 and m.get('profile_deceleration')==100 for m in profiles)
        checks['pick_request']=len(moves)>=1 and moves[0].get('axes')==[0,1,2] and moves[0].get('positions')==[.5,.6,.7]
        checks['move_velocities']=all(m.get('profile_velocities')==[5,5,2] for m in moves)
        if case=='normal':
            checks['success_exit']=process.returncode==0
            checks['two_moves']=len(moves)==2 and moves[-1].get('positions')==[1,1.1,1.2]
            checks['output_sequence']=[(m.get('slot'),m.get('kind'),m.get('channel'),m.get('value')) for m in outputs]==[
                (1,'digital',0,True),(2,'analog',0,100),(1,'digital',0,False),(2,'analog',0,0)]
            second=[r for r in proxy.records if r['direction']=='request' and r['data']['cmd']=='system/axes/move_abs'][1:]
            checks['input_gate']=bool(input_time and second and second[0]['time']>=input_time)
            checks['final_position']=motion_complete(final,[1,1.1,1.2])
        else:
            checks['no_place']=len(moves)==1
            checks['no_release_output']=len(outputs)==(0 if case in ('api_fail','response_timeout') else 2)
            checks['not_success_exit']=process.returncode!=0
        # Verify completion independently at every grasp/release command boundary.
        last=None
        output_number=0
        boundaries=True
        for record in proxy.records:
            value=record['data']
            if record['direction']=='server' and value.get('type')=='system/feedback':
                last=value
            if record['direction']=='request' and value['cmd']=='system/io/output_write':
                expected=[.5,.6,.7] if output_number<2 else [1,1.1,1.2]
                boundaries=boundaries and motion_complete(last,expected)
                output_number+=1
        checks['completion_before_outputs']=boundaries
        if case not in ('fault','connection_loss','authority_loss'):
            checks['stop_requested']=any(m['cmd']=='system/axes/stop' for m in requests)
            checks['authority_released']=any(m['cmd']=='system/authority/release' for m in requests)
        if case in ('input_timeout','stop'):
            checks['outputs_retained']=io_output(final,1,'digital') is True and io_output(final,2,'analog')==100
        if case=='fault':
            checks['fault_observed']=bool(final and final['server_health']['fault_count']>0)
        result={'case':case,'exit_code':process.returncode,'checks':checks,'schema_errors':errors,
                'model_tokens':{'additional_model_calls':0,'input_tokens':0,'output_tokens':0,
                                'note':'Deterministic execution; generation usage recorded separately, evaluator conversation excluded'},
                'passed':all(checks.values()),'duration':time.monotonic()-started,'command':command}
        (case_dir/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (case_dir/'trace.json').write_text(json.dumps(proxy.records),encoding='utf-8')
        (case_dir/'final-feedback.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
        results.append(result)
        print(json.dumps(result),flush=True)
    except Exception as exc:
        result={'case':case,'harness_error':repr(exc),'passed':False}
        results.append(result)
        print(json.dumps(result),flush=True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        if proxy:
            proxy.close()
        fixture.log.flush()
        shutil.copy2(fixture.folder/'server.log',case_dir/'server.log')
        fixture.cleanup()
    (report/'evaluation-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
