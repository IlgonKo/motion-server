"""Bounded real Tk callback tests against the authorized Mock endpoint only."""
import json
from pathlib import Path
import time
import tkinter as tk
from motion_server_reference_client import MotionServerClient
from .gui import Panel
from .settings import load_config


def observe():
    client=MotionServerClient('127.0.0.1',52728,feedback_queue_size=1)
    client.start()
    try:
        assert client.wait_connected(5)
        status=client.request({'cmd':'system/authority/status'},timeout=5)
        feedback=client.get_feedback(timeout=2)
        modules=next(d for d in feedback['io']['devices'] if d['id']=='io0')['modules']
        do=next(m for m in modules if m['slot']==1)['outputs']['digital'][0]
        ao=next(m for m in modules if m['slot']==2)['outputs']['analog'][0]
        return {'authority':status,'positions':feedback['actual_positions'],'statuswords':feedback['statuswords'],'DO':do,'AO':ao}
    finally:
        client.stop()


def case(mode):
    root=tk.Tk()
    panel=Panel(root)
    stage='connect'
    start=time.monotonic()
    failures=[]
    focus_tested=False
    duplicate_tested=False
    heartbeat=0
    def drive():
        nonlocal stage,focus_tested,duplicate_tested,heartbeat
        heartbeat+=1
        try:
            if time.monotonic()-start>35:
                raise TimeoutError('GUI test deadline')
            if stage=='connect':
                panel.buttons['Connect'].invoke()
                stage='authority'
            elif stage=='authority' and not panel.busy:
                assert panel.metadata_ok, panel.history
                panel.buttons['Request authority'].invoke()
                stage='run'
            elif stage=='run' and not panel.busy:
                value=panel.feedback.snapshot()[2] or {}
                if value.get('command_authority',{}).get('owned_by_this_client'):
                    # Use the same callback as the visible button, including duplicate guard.
                    panel.run()
                    seq=panel.sequence
                    panel.run()
                    assert panel.sequence is seq
                    duplicate_tested=True
                    stage='motion'
            elif stage=='motion':
                seq=panel.sequence
                if seq and seq.step=='Move pick' and seq.state=='running' and not focus_tested:
                    root.event_generate('<FocusOut>')
                    assert not seq.cancel.is_set(), 'Non-Teaching focus change must not invent Jog/Stop'
                    focus_tested=True
                if mode in ('stop','close') and seq and seq.step=='Move place' and seq.state=='running':
                    if mode=='stop': panel.buttons['Stop'].invoke()
                    else: root.tk.call('eval',root.protocol('WM_DELETE_WINDOW'))
                    stage='finish'
                elif mode=='complete' and not panel.busy:
                    stage='finish'
            elif stage=='finish' and not panel.busy:
                expected='completed' if mode=='complete' else 'cancelled'
                assert panel.sequence.state==expected,(panel.sequence.state,panel.history)
                assert panel.sequence.cleanup_confirmed,panel.history
                if mode!='close':
                    assert panel.feedback.snapshot()[2]['command_authority']['owned_by_this_client'], 'GUI must retain authority after Run'
                    panel.close()
                stage='closing'
        except Exception as exc:
            failures.append(repr(exc))
            panel.close()
            stage='closing'
        if not panel.closed:
            root.after(15,drive)
    root.after(50,drive)
    root.mainloop()
    assert panel.closed
    expected='completed' if mode=='complete' else 'cancelled'
    assert panel.sequence and panel.sequence.state==expected,(mode,panel.history)
    assert panel.sequence.cleanup_confirmed
    assert not failures,failures
    assert focus_tested and duplicate_tested
    actual=observe()
    assert all(not w&256 for w in actual['statuswords'][:3]),actual
    assert actual['authority']['data']['available'],actual
    if mode=='complete':
        assert actual['positions'][:3]==[100,110,120],actual
        assert actual['DO'] is False and actual['AO']==0,actual
    else:
        assert actual['DO'] is True and actual['AO']==100,actual
    return {'case':mode,'state':panel.sequence.state,'stop_confirmed':True,'focus_loss_no_jog':focus_tested,'duplicate_run_blocked':duplicate_tested,'ui_heartbeats':heartbeat,'elapsed_seconds':round(time.monotonic()-start,3),'after_disconnect':actual,'logs':panel.history}

if __name__=='__main__':
    config=load_config()
    assert (config['host'],config['port'])==('127.0.0.1',52728)
    results=[]
    for mode in ('complete','stop','close'):
        result=case(mode)
        results.append(result)
        Path('generated/gui_result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(mode, result['state'], 'Stop confirmed; window closed',flush=True)
    print('All GUI Mock tests passed; no test window remains.',flush=True)
