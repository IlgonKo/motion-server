"""Deliver SIGINT on the main Python thread without modifying submitted code."""
import _thread
import runpy
import sys
import threading
import time
from pathlib import Path

marker = Path(sys.argv[1])
target = sys.argv[2]
sys.argv = sys.argv[2:]
sys.path.insert(0,str(Path(target).parent))
# Test-only authority loss injection uses a real release on the target connection.
sys.path.insert(0,str(Path.cwd()/'reference_clients/python'))
from motion_server_reference_client import MotionServerClient
clients = []
start = MotionServerClient.start
def observed_start(self):
    clients.append(self)
    return start(self)
MotionServerClient.start = observed_start
def watch():
    released = False
    while not marker.exists():
        if not released and marker.with_suffix('.authority').exists() and clients:
            released = True
            try:
                clients[0].request({'cmd':'system/authority/release'})
            except Exception as exc:
                print('EVALUATOR_AUTHORITY_RELEASE_FAILED',repr(exc),flush=True)
        time.sleep(.02)
    _thread.interrupt_main()
threading.Thread(target=watch,daemon=True).start()
runpy.run_path(target,run_name='__main__')
