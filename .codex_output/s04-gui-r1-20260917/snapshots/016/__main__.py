"""One-shot CLI. Run from workspace: python -m generated --run."""
import argparse
import signal
import time
from motion_server_reference_client import MotionServerClient
from .sequence import Feedback, Sequence, success
from .settings import CONFIG, load_config, check_metadata

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(CONFIG))
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    if args.gui:
        from .gui import show
        show(args.config)
        return 0
    if not args.run:
        parser.error('Use --run for one cycle or --gui')
    config = load_config(args.config)
    client = MotionServerClient(config['host'], config['port'], request_timeout=config['request_timeout'], feedback_queue_size=1)
    feed = Feedback(client)
    sequence = None
    interrupted = False
    result = 1
    def cancel(*_):
        nonlocal interrupted
        interrupted = True
        if sequence:
            sequence.cancel.set()
    previous = signal.signal(signal.SIGINT, cancel)
    try:
        client.start()
        feed.start()
        if not client.wait_connected(config['request_timeout']):
            raise RuntimeError(client.last_error)
        print('Metadata:', check_metadata(success(client.request({'cmd':'system/axes/status'})), config))
        if interrupted:
            return 1
        authority = success(client.request({'cmd':'system/authority/request'}))
        if not authority.get('owned_by_this_client'):
            raise RuntimeError(f'Authority denied: {authority}')
        deadline = time.monotonic() + config['feedback_timeout']
        while time.monotonic() < deadline:
            value = feed.snapshot()[2] or {}
            if value.get('command_authority', {}).get('owned_by_this_client'):
                break
            time.sleep(.02)
        sequence = Sequence(client, feed, config, {}, print)
        if interrupted:
            sequence.cancel.set()
        result = 0 if sequence.run() == 'completed' else 1
    except Exception as exc:
        print('FAILED:', exc)
    finally:
        try:
            if client.is_connected:
                owned = success(client.request({'cmd':'system/authority/status'}))
                if owned.get('owned_by_this_client'):
                    success(client.request({'cmd':'system/authority/release'}))
                    print('Authority released')
            else:
                print('Disconnected: explicit authority release unavailable')
                result = 1
        except Exception as exc:
            print('Shutdown incomplete:', exc)
            result = 1
        finally:
            client.stop()
            feed.close()
            signal.signal(signal.SIGINT, previous)
    return result

if __name__ == '__main__':
    raise SystemExit(main())
