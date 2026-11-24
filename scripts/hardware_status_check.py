"""Explicit read-only TCP hardware profile; no master, authority or motion commands."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'reference_clients/python'))
from motion_server_reference_client import MotionServerClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    client = MotionServerClient(args.host, args.port, request_timeout=5)
    report = {'host': args.host, 'port': args.port, 'responses': [], 'error': None}
    try:
        client.start()
        if not client.wait_connected(5):
            raise ConnectionError('TCP connection timed out')
        for command in ('system/server/status', 'system/bus/status'):
            response = client.request({'cmd': command})
            report['responses'].append(response)
            if response.get('result') != 'success':
                raise RuntimeError(f'{command} failed')
        server, bus = [r['data'] for r in report['responses']]
        if not (server.get('initialized') and bus.get('connected') and bus.get('wkc_ok')):
            raise RuntimeError('Server/bus is not ready or WKC is not valid')
    except Exception as error:
        report['error'] = str(error)
    finally:
        client.stop()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Read-only status check: {report["error"] or "passed"}')
    return bool(report['error'])


if __name__ == '__main__':
    raise SystemExit(main())
