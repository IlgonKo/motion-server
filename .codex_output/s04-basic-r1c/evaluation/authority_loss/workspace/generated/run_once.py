"""PowerShell: & <python.exe> -B generated/run_once.py --run-mock"""
import argparse
import json
from pathlib import Path
import signal
import sys
import threading

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'reference_clients' / 'python'))
from motion_server_reference_client import MotionServerClient
from sequence import run


def main():
    parser = argparse.ArgumentParser(description='One Pick & Place on the authorized Mock server')
    parser.add_argument('--run-mock', action='store_true', required=True)
    parser.add_argument('--settings', type=Path, default=ROOT / 'settings.json')
    args = parser.parse_args()
    c = json.loads(args.settings.read_text(encoding='utf-8'))
    cancel = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: cancel.set())
    client = MotionServerClient(c['host'], c['port'], request_timeout=c['request_timeout'], feedback_queue_size=100)
    report = run(client, c, cancel)
    path = ROOT / ('run-' + str(__import__('time').time_ns()) + '.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'state': report['state'], 'cleanup_complete': report['cleanup_complete'], 'report': str(path)}))
    return 0 if report['state'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
