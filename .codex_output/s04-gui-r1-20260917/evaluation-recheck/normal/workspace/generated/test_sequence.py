import copy
import json
from pathlib import Path
import queue
import threading
import time
import unittest
from .sequence import Feedback, Sequence, input_matches
from .settings import load_config

class FakeClient:
    """Deterministic client double only; no server/transport implementation."""
    def __init__(self, mode='normal'):
        self.mode=mode
        self.is_connected=True
        self.calls=[]
        self.queue=queue.Queue()
        self.done=threading.Event()
        self.lock=threading.Lock()
        self.f={'process_data_valid':True,'actual_positions':[0.,0.,0.], 'target_positions':[0.,0.,0.], 'statuswords':[1024]*3,
                'server_health':{'fault_count':0},'command_authority':{'owned_by_this_client':True},
                'io':{'devices':[{'id':'io0','modules':[{'slot':3,'inputs':{'digital':[True]}},{'slot':4,'inputs':{'analog':[100]}}]}]}}
        self.moved=False
        self.move_at=0
        self.thread=threading.Thread(target=self.produce,daemon=True)
        self.thread.start()
    def produce(self):
        while not self.done.wait(.005):
            with self.lock:
                if self.moved and time.monotonic()-self.move_at>.06:
                    self.f['actual_positions']=list(self.f['target_positions'])
                    self.f['statuswords']=[1024]*3
                    if self.mode=='one_axis': self.f['statuswords'][2]=256
                    if self.mode=='missing_axis': self.f['actual_positions']=self.f['actual_positions'][:2]
                    if self.mode=='fault': self.f['statuswords'][1]|=8
                    if self.mode=='invalid': self.f['process_data_valid']=False
                    if self.mode=='authority': self.f['command_authority']['owned_by_this_client']=False
                    if self.mode=='disconnect': self.is_connected=False
                    if self.mode=='input': self.f['io']['devices'][0]['modules'][1]['inputs']['analog'][0]=0
                if self.moved and self.mode=='stale': continue
                if self.is_connected: self.queue.put(copy.deepcopy(self.f))
    def get_feedback(self,timeout=None): return self.queue.get(timeout=timeout)
    def request(self,message,timeout=None):
        self.calls.append(copy.deepcopy(message))
        cmd=message['cmd']
        if cmd=='system/authority/status':
            return {'result':'success','data':copy.deepcopy(self.f['command_authority'])}
        if cmd=='system/axes/move_abs':
            if self.mode=='fail': return {'result':'fail','failure':{'code':'TEST_FAIL','message':'injected','details':{'axis':2}}}
            if self.mode=='request_timeout': raise TimeoutError('injected request timeout; may have executed')
            with self.lock:
                self.f['target_positions']=list(message['positions'])
                self.f['statuswords']=[256]*3
                self.moved=True
                self.move_at=time.monotonic()
        if cmd=='system/axes/stop':
            if self.mode=='stop_fail': return {'result':'fail','failure':{'code':'STOP_FAIL','message':'injected'}}
            with self.lock:
                self.moved=False
                self.f['process_data_valid']=True
                self.f['statuswords']=[1024]*3
        return {'result':'success','data':{}}
    def close(self):
        self.done.set()
        self.thread.join(1)

class Tests(unittest.TestCase):
    def setup_run(self,mode='normal',report=None):
        c=load_config()
        c.update(request_timeout=.2,stage_timeout=.24,input_timeout=.15,feedback_timeout=.12)
        client=FakeClient(mode)
        feed=Feedback(client)
        feed.start()
        self.addCleanup(client.close)
        self.addCleanup(feed.close)
        end=time.monotonic()+1
        while feed.snapshot()[2] is None and time.monotonic()<end: time.sleep(.005)
        logs=[]
        s=Sequence(client,feed,c,{},report or logs.append)
        return client,feed,s,logs
    def test_normal_and_schema_contract(self):
        c,f,s,logs=self.setup_run()
        self.assertEqual(s.run(),'completed')
        self.assertTrue(s.cleanup_confirmed)
        cmds=[x['cmd'] for x in c.calls]
        self.assertEqual(cmds,['system/axis/profile']*3+['system/axes/move_abs']+['system/io/output_write']*2+['system/axes/move_abs']+['system/io/output_write']*2+['system/authority/status','system/axes/stop'])
        schemas={}
        for path in (Path(__file__).resolve().parents[1]/'motion_server/api/schema').glob('*.json'):
            schemas.update(json.loads(path.read_text())['$defs'])
        for request in c.calls:
            schema=schemas[request['cmd'].replace('/','_')]
            self.assertTrue(set(schema['required'])<=set(request))
            self.assertTrue(set(request)<=set(schema['properties']))
            if request['cmd'].endswith('move_abs'):
                self.assertIn('profile_velocities',request)
                self.assertNotIn('velocities',request)
        self.assertEqual([x['value'] for x in c.calls if 'value' in x],[True,100,False,0])
    def test_fail_timeout_loss_and_fault(self):
        for mode in ['fail','request_timeout','authority','disconnect','fault','stale','invalid','missing_axis','one_axis','input','stop_fail']:
            with self.subTest(mode=mode):
                c,f,s,logs=self.setup_run(mode)
                self.assertEqual(s.run(),'failed')
                if mode not in ('stop_fail',):
                    self.assertLessEqual(sum(x['cmd'].endswith('move_abs') for x in c.calls),1)
                if mode in ('authority','disconnect','stop_fail'):
                    self.assertFalse(s.cleanup_confirmed)
                    self.assertTrue(any('NOT confirmed' in x for x in logs))
                self.assertFalse(any(x['cmd'].endswith(('disable','home','fault_reset','authority/request')) for x in c.calls))
                c.close(); f.close()
    def test_cancel_preserves_grasp_outputs(self):
        c,f,s,logs=self.setup_run()
        def report(line):
            logs.append(line)
            if line=='Move place': s.cancel.set()
        s.report=report
        self.assertEqual(s.run(),'cancelled')
        self.assertTrue(s.cleanup_confirmed)
        self.assertEqual([x['value'] for x in c.calls if 'value' in x],[True,100])
        self.assertEqual(sum(x['cmd'].endswith('move_abs') for x in c.calls),1)
    def test_cancel_in_flight_request_is_not_retracted(self):
        c,f,s,logs=self.setup_run()
        request=c.request
        def delayed(message,timeout=None):
            if message['cmd'].endswith('move_abs'):
                s.cancel.set()
                time.sleep(.03)
            return request(message,timeout)
        c.request=delayed
        self.assertEqual(s.run(),'cancelled')
        self.assertTrue(any(x['cmd'].endswith('move_abs') for x in c.calls))
        self.assertFalse(any(x['cmd'].endswith('output_write') for x in c.calls))
        self.assertTrue(s.cleanup_confirmed)
    def test_no_duplicate_or_resume(self):
        c,f,s,logs=self.setup_run()
        s.running.acquire()
        with self.assertRaises(RuntimeError): s.run()
        s.running.release()
        self.assertEqual(s.run(),'completed')
        with self.assertRaises(RuntimeError): s.run()
    def test_invalid_config(self):
        c=load_config(); c['pick']['positions'].pop('Z')
        with self.assertRaises(KeyError): Sequence(None,None,c,{})
        c=load_config(); c['roles'].pop('Z')
        with self.assertRaises(ValueError): Sequence(None,None,c,{})
    def test_fault_during_cleanup_is_not_completed(self):
        c,f,s,logs=self.setup_run()
        original=c.request
        def request(message,timeout=None):
            response=original(message,timeout)
            if message['cmd']=='system/axes/stop':
                with c.lock: c.f['statuswords'][2]|=8
            return response
        c.request=request
        self.assertEqual(s.run(),'failed')
        self.assertTrue(s.cleanup_confirmed)
    def test_inputs_require_both_and_correct_station(self):
        c,f,s,logs=self.setup_run()
        data=copy.deepcopy(c.f)
        conditions=s.config['grasp_conditions']
        self.assertTrue(input_matches(data,conditions))
        data['io']['devices'][0]['modules'][1]['inputs']['analog'][0]=49
        self.assertFalse(input_matches(data,conditions))
        data['io']['devices'][0]['id']='other'
        self.assertFalse(input_matches(data,conditions))
    def test_old_snapshot_and_invalid_do_not_satisfy(self):
        c,f,s,logs=self.setup_run()
        c.done.set(); c.thread.join(1)
        baseline=f.barrier()
        with self.assertRaises((RuntimeError,TimeoutError)): s.wait(lambda _:True,baseline,.2)
    def test_snapshot_is_frozen(self):
        c,f,s,logs=self.setup_run()
        source=load_config(); original=copy.deepcopy(source)
        run=Sequence(c,f,source,{})
        source['pick']['positions']['X']=999
        self.assertEqual(run.config,original)

if __name__=='__main__': unittest.main(verbosity=2)
