"""In-process restart over real TCP against an isolated Mock child process."""
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference_clients/python'))
from motion_server_reference_client import MotionServerClient
from motion_server_reference_client.exceptions import ConnectionLostError

LAUNCH = r'''
import json, os, sys, threading, time
from pathlib import Path
from configuration import ConfigurationSource
from motion_server.application import MotionServerApplication
from motion_server import server
from device.virtual_device.parameter_store.store import ParameterStore
from ethercat.exceptions import EtherCATDiscoveryException
root = Path(sys.argv[1])
original = server.connect_bus
def connect(runtime):
    if (root/'bus-fail').exists(): raise EtherCATDiscoveryException('mock-test', 1, -1)
    original(runtime)
server.connect_bus = connect
save = ParameterStore.save
def slow_save(self, *args):
    (root/'saving').touch()
    time.sleep(.5)
    return save(self, *args)
ParameterStore.save = slow_save
run = MotionServerApplication._run
def audit(self, runner=None):
    try: return run(self, runner)
    finally:
        with (root/'sessions.jsonl').open('a') as out:
            out.write(json.dumps({'pid': os.getpid(), 'threads': [t.name for t in threading.enumerate()]})+'\n')
MotionServerApplication._run = audit
sys.exit(MotionServerApplication.from_source(ConfigurationSource(root), environ={}).run())
'''


class ServerRestartTcpTest(unittest.TestCase):
    def test_restart_reload_failures_pending_save_and_resource_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
            def config(extra=''):
                (root/'.env').write_text(f'''MOTION_SERVER_BACKEND=mock
MOTION_SERVER_BUS=0:axis:cmmt-as
MOTION_SERVER_PORT={port}
MOTION_SERVER_CMMT_SLAVE_NON_PDO_CONFIGURATIONS=0:linear_mm
MOTION_SERVER_LOG_FILE_ENABLED=1
MOTION_SERVER_LOG_FILE_PATH=server.log
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_ENABLED=1
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH=parameters.sqlite
MOTION_SERVER_VIRTUAL_DEVICE_STORAGE_IDS=0:axis_x
PYSOEM_CYCLE_TIME=0.01
{extra}
''', encoding='utf-8')
            config()
            env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8')
            with (root/'console.log').open('w+', encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable, '-B', '-c', LAUNCH, str(root)],
                                           cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                client = None
                def connect():
                    c = MotionServerClient('127.0.0.1', port, request_timeout=5)
                    c.start()
                    if not c.wait_connected(10):
                        c.stop(); self.fail('Server not available')
                    return c
                def request(cmd, **args):
                    response = client.request({'cmd': cmd, **args})
                    self.assertEqual(response['result'], 'success', response)
                    return response.get('data', {})
                def sessions():
                    path = root/'sessions.jsonl'
                    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
                def restart():
                    nonlocal client
                    before = len(sessions())
                    request('system/server/restart')
                    client.stop()
                    end = time.monotonic()+10
                    while len(sessions()) <= before and time.monotonic()<end: time.sleep(.01)
                    self.assertGreater(len(sessions()), before)
                    self.assertIsNone(process.poll(), 'Restart replaced/exited the process')
                    client = connect()
                try:
                    client = connect()
                    self.assertTrue(request('system/server/status')['initialized'])
                    request('system/authority/request')
                    request('system/axis/param_write', axis=0, index=0x6083, subindex=0, data_type='uint32', value=2233)
                    with concurrent.futures.ThreadPoolExecutor(1) as pool:
                        pending = pool.submit(client.request, {'cmd':'system/axis/param_save', 'axis':0})
                        end=time.monotonic()+5
                        while not (root/'saving').exists() and time.monotonic()<end: time.sleep(.005)
                        self.assertTrue((root/'saving').exists())
                        restart()
                        try: pending.result(timeout=5)
                        except ConnectionLostError: pass  # Old connection is explicitly closed.
                    self.assertEqual(request('system/axis/param_read', axis=0,index=0x6083,subindex=0,data_type='uint32')['value'],2233)
                    # Unrequested authority must not survive reconnect.
                    denied=client.request({'cmd':'system/server/restart'})
                    self.assertEqual(denied['result'],'fail')
                    for _ in range(4):
                        request('system/authority/request'); restart()
                    request('system/authority/request')
                    config('MOTION_SERVER_CSP_VELOCITY_OFFSET=invalid')
                    restart()
                    status=request('system/server/status')
                    self.assertFalse(status['initialized'])
                    request('system/authority/request'); config(); restart()
                    self.assertEqual(request('system/server/status')['diagnostic_status']['level'],'normal')
                    request('system/authority/request')
                    (root/'bus-fail').touch(); restart()
                    self.assertFalse(request('system/server/status')['initialized'])
                    request('system/authority/request'); (root/'bus-fail').unlink(); restart()
                    self.assertTrue(request('system/server/status')['initialized'])
                    # Reload a colliding port: exit nonzero rather than reuse old settings.
                    with socket.socket() as occupied:
                        occupied.bind(('127.0.0.1',0)); occupied.listen()
                        request('system/authority/request')
                        config(f'MOTION_SERVER_PORT={occupied.getsockname()[1]}')
                        request('system/server/restart')
                        self.assertEqual(process.wait(timeout=10),1)
                    records=sessions()
                    self.assertGreaterEqual(len(records),10)
                    self.assertEqual({r['pid'] for r in records},{process.pid})
                    for r in records:
                        self.assertFalse(any('virtual' in n.lower() for n in r['threads']),r)
                        self.assertLessEqual(r['threads'].count('motion-file-log'),1)
                    # Both OS locks must be reusable after final exit.
                    from device.virtual_device.parameter_store.store import StoreLock
                    with StoreLock(root/'parameters.sqlite'): pass
                    log.flush(); log.seek(0)
                    self.assertNotIn('Traceback',log.read())
                finally:
                    if client is not None: client.stop()
                    if process.poll() is None: process.terminate(); process.wait(timeout=5)
                    if not self._outcome.success:
                        log.flush(); log.seek(0); print(log.read())
