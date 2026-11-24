"""Real TCP / isolated mock server persistence contract; no physical EtherCAT."""
import concurrent.futures
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


class VirtualParameterStoreTcpTest(unittest.TestCase):
    def test_slow_commit_keeps_tcp_responsive_and_restores_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            (folder / '.env').write_text(f'''MOTION_SERVER_BACKEND=mock
MOTION_SERVER_MODE=basic
MOTION_SERVER_PORT={port}
MOTION_SERVER_BUS=0:axis:cmmt-as
MOTION_SERVER_CMMT_SLAVE_NON_PDO_CONFIGURATIONS=0:linear_mm
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_ENABLED=1
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH=parameters.sqlite
MOTION_SERVER_VIRTUAL_DEVICE_STORAGE_IDS=0:axis_x
PYSOEM_CYCLE_TIME=0.002
PYSOEM_DC_ENABLED=0
''')
            env = {k: v for k, v in os.environ.items() if not k.startswith(
                ('MOTION_SERVER_', 'PYSOEM_', 'MOCK_', 'AXIS_'))}
            env['PYTHONPATH'] = str(ROOT)
            code = '''import sys, time
from pathlib import Path
from configuration import ConfigurationSource
from motion_server.application import MotionServerApplication
from device.virtual_device.parameter_store.store import ParameterStore
original = ParameterStore.save
def slow_save(self, *args):
    (Path(sys.argv[1]) / 'saving').touch()
    time.sleep(0.5)
    return original(self, *args)
ParameterStore.save = slow_save
MotionServerApplication.from_source(ConfigurationSource(project_root=Path(sys.argv[1])), argv=[]).run()
'''
            for generation in range(2):
                with (folder / f'server-{generation}.log').open('w+', encoding='utf-8') as log:
                    process = subprocess.Popen([sys.executable, '-B', '-u', '-c', code, str(folder)],
                        cwd=folder, env=env, stdout=log, stderr=subprocess.STDOUT)
                    client = MotionServerClient('127.0.0.1', port, request_timeout=3)
                    observer = MotionServerClient('127.0.0.1', port, request_timeout=3)
                    try:
                        client.start()
                        observer.start()
                        self.assertTrue(client.wait_connected(10))
                        self.assertTrue(observer.wait_connected(10))
                        def request(command, **args):
                            response = client.request({'cmd': command, **args})
                            self.assertEqual(response['result'], 'success', response)
                            return response.get('data', {})
                        self.assertTrue(request('system/server/status')['initialized'])
                        if generation == 0:
                            request('system/authority/request')
                            request('system/axis/param_write', axis=0, index=0x6083,
                                    subindex=0, data_type='uint32', value=2233)
                            with concurrent.futures.ThreadPoolExecutor(1) as executor:
                                saved = executor.submit(request, 'system/axis/param_save', axis=0)
                                deadline = time.monotonic() + 3
                                while not (folder / 'saving').exists() and time.monotonic() < deadline:
                                    time.sleep(.005)
                                self.assertTrue((folder / 'saving').exists())
                                self.assertFalse(saved.done())
                                status = observer.request({'cmd': 'system/server/status'})
                                self.assertEqual(status['result'], 'success')
                                self.assertFalse(saved.done(), 'status was blocked behind disk commit')
                                saved.result(timeout=3)
                            # More than two heartbeat timeout periods elapsed during the save.
                            self.assertTrue(request('system/server/status')['initialized'])
                        else:
                            data = request('system/axis/param_read', axis=0, index=0x6083,
                                           subindex=0, data_type='uint32')
                            self.assertEqual(data['value'], 2233)
                    finally:
                        client.stop()
                        observer.stop()
                        process.terminate()
                        process.wait(timeout=5)
                        log.flush()
                        log.seek(0)
                        output = log.read()
                        if not self._outcome.success:
                            print(output)
                    self.assertNotIn('Traceback', output)
