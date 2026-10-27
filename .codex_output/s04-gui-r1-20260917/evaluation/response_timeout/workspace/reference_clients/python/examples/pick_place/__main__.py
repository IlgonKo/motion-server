import argparse
from pathlib import Path
import signal
import time

from motion_server_reference_client import MotionServerClient
from .program import Feedback, Sequence, load_json, success


def main():
    parser = argparse.ArgumentParser(description="AI reference Pick & Place (user-configured hardware only)")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("sequence.json"))
    parser.add_argument("--points", type=Path, default=Path(__file__).with_name("teaching_points.json"))
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--run", action="store_true", help="Explicitly execute one configured sequence")
    args = parser.parse_args()
    if args.gui:
        from .gui import show
        show(args.config, args.points)
        return 0
    if not args.run:
        parser.error("Use --gui or explicitly --run after checking configuration and travel path")
    config = load_json(args.config)
    points = load_json(args.points) if config["teaching"] else {}
    client = MotionServerClient(config["host"], config["port"], request_timeout=config["request_timeout"])
    feedback = Feedback(client)
    sequence = None
    interrupted = False

    def cancel(*_):
        nonlocal interrupted
        interrupted = True
        if sequence:
            sequence.cancel.set()

    old_handler = signal.signal(signal.SIGINT, cancel)
    client.start()
    feedback.start()
    try:
        if not client.wait_connected(timeout=config["request_timeout"]):
            raise RuntimeError(client.last_error)
        if interrupted:
            return 1
        success(client.request({"cmd": "system/authority/request"}))
        deadline = time.monotonic() + config["feedback_timeout"]
        while time.monotonic() < deadline:
            value = feedback.snapshot()[2]
            if interrupted:
                return 1
            if value and value.get("command_authority", {}).get("owned_by_this_client"):
                break
            time.sleep(0.02)
        sequence = Sequence(client, feedback, config, points)
        if interrupted:
            sequence.cancel.set()
        return 0 if sequence.run() == "completed" else 1
    finally:
        try:
            value = feedback.snapshot()[2]
            if client.is_connected and value and value.get("command_authority", {}).get("owned_by_this_client"):
                success(client.request({"cmd": "system/authority/release"}))
        finally:
            client.stop()
            feedback.close()
            signal.signal(signal.SIGINT, old_handler)


if __name__ == "__main__":
    raise SystemExit(main())
