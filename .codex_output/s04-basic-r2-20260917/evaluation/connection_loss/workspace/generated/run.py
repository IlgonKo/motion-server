"""CLI entry point. No install and no files written outside generated/."""
import argparse
import json
from pathlib import Path
import signal
import sys
import threading
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference_clients/python'))
from motion_server_reference_client import MotionServerClient
from sequence import Feedback, Sequence, Cancelled, axes_complete, prepare, success


def main():
    parser = argparse.ArgumentParser(description='Run one Pick & Place on the authorized Mock server')
    parser.add_argument('--run-mock', action='store_true', help='Execute exactly one Mock sequence')
    args = parser.parse_args()
    if not args.run_mock: parser.error('Explicit --run-mock required')
    c = prepare(json.loads(Path(__file__).with_name('settings.json').read_text(encoding='utf-8')))
    if (c['host'], c['port']) != ('127.0.0.1', 62554):
        raise ValueError('This entry point is restricted to the authorized Mock address')
    # User identifies this as the actual applied file. Do not invent a config parser/merge.
    config_text = (ROOT / 'config.txt').read_text(encoding='utf-8-sig')
    if 'MOTION_SERVER_BACKEND=mock' not in config_text.splitlines():
        raise ValueError('Provided config no longer identifies the authorized Mock')
    client = MotionServerClient(c['host'], c['port'], request_timeout=c['request_timeout'])
    cancel = threading.Event()
    old = signal.signal(signal.SIGINT, lambda *_: cancel.set())
    feedback = Feedback(client, list(c['roles'].values()))
    messages = []
    def report(message):
        line = f'{time.monotonic():.6f} {message}'
        messages.append(line)
        print(line, flush=True)
    sequence = Sequence(client, feedback, c, cancel, report)
    acquired = False
    authority_attempted = False
    release_confirmed = False
    result = 'failed'
    metadata = None
    try:
        client.start()
        if not client.wait_connected(timeout=c['request_timeout']): raise RuntimeError(client.last_error)
        feedback.start()
        if cancel.is_set(): raise Cancelled('Stop before setup')
        metadata = success(client.request({'cmd': 'system/axes/status'}, timeout=c['request_timeout']))['axis_metadata']
        for role, axis in c['roles'].items():
            m = next((v for v in metadata if v.get('axis') == axis), None)
            if m is None or any(m.get(k) != v for k, v in c['expected_units'].items()):
                raise ValueError(f'{role}: missing/mismatched metadata units; no motion')
            report(f'{role}=axis {axis}: {m["position_unit"]}, {m["velocity_unit"]}, {m["acceleration_unit"]}')
        if cancel.is_set(): raise Cancelled('Stop before authority request')
        authority_attempted = True
        authority = success(client.request({'cmd': 'system/authority/request'}, timeout=c['request_timeout']))
        acquired = authority['owned_by_this_client'] and authority['granted']
        if not acquired: raise RuntimeError('Authority not granted: ' + json.dumps(authority))
        after = feedback.barrier(c['feedback_timeout'])
        deadline = time.monotonic() + c['feedback_timeout']
        while True:
            if cancel.is_set(): raise Cancelled('Stop during authority setup')
            serial, received, f, loss, _ = feedback.snapshot()
            if loss or not client.is_connected: raise RuntimeError(loss or 'Disconnected')
            if serial > after and f and f.get('command_authority', {}).get('owned_by_this_client'): break
            if time.monotonic() >= deadline: raise TimeoutError('Authority Feedback timeout')
            cancel.wait(0.01)
        result = sequence.run()
    except Exception as exc:
        result = 'cancelled' if isinstance(exc, Cancelled) else 'failed'
        report(f'{type(exc).__name__}: {exc}')
    finally:
        try:
            if authority_attempted:
                if not client.is_connected or feedback.snapshot()[3]:
                    raise RuntimeError('Connection/authority lost; no commands on a new session')
                owner = success(client.request({'cmd': 'system/authority/status'}, timeout=c['request_timeout']))
                if owner['owned_by_this_client']:
                    # Covers cancellation/setup failure and uncertain authority-request timeout.
                    try:
                        if sequence.state == 'idle':
                            success(client.request({'cmd': 'system/axes/stop', 'axes': sequence.axes}, timeout=c['request_timeout']))
                            after = feedback.barrier(c['feedback_timeout'])
                            sequence.wait(lambda f: axes_complete(f, sequence.axes), after, c['move_timeout'], cleanup=True)
                            sequence.stop_confirmed = True
                            report('Setup cleanup: Stop confirmed; outputs retained')
                    finally:
                        if client.is_connected and not feedback.snapshot()[3]:
                            released = success(client.request({'cmd': 'system/authority/release'}, timeout=c['request_timeout']))
                            if released['owned_by_this_client']: raise RuntimeError('Authority release not confirmed')
                            release_confirmed = True
                            report('Authority released')
                        else:
                            raise RuntimeError('Authority release unavailable after connection/authority loss')
                elif acquired:
                    raise RuntimeError('Authority lost before release')
        except Exception as exc:
            result = 'failed'
            report(f'INCOMPLETE cleanup/release: {exc}')
        finally:
            client.stop()
            if feedback.thread.is_alive(): feedback.close()
            signal.signal(signal.SIGINT, old)
        if cancel.is_set() and result == 'completed': result = 'cancelled'
        report('CLI result: ' + result)
        Path(__file__).with_name('last_run.json').write_text(json.dumps({
            'result': result, 'stop_confirmed': sequence.stop_confirmed,
            'release_confirmed': release_confirmed, 'settings': c,
            'axis_metadata': metadata, 'messages': messages, 'evidence': sequence.evidence
        }, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0 if result == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
