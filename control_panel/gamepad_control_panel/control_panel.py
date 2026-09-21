import argparse
import json
from pathlib import Path
import sys

from motion_server_reference_client import MotionServerClient

from control_panel.gamepad_control_panel.config import load_config
from control_panel.gamepad_control_panel.controller import PendantController
from control_panel.gamepad_control_panel.gui import show
from control_panel.gamepad_control_panel.input import (
    PygameJoystickAdapter,
    list_pygame_devices,
)


def default_config_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"
    return Path(__file__).parent / "config.json"


def main():
    parser = argparse.ArgumentParser(description="Motion Server Windows Gamepad Control Panel")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
    )
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()
    if args.list_devices:
        print(json.dumps(list_pygame_devices(), indent=2, ensure_ascii=False))
        return 0
    config = load_config(args.config)
    client = MotionServerClient(
        config.host,
        config.port,
        request_timeout=config.request_timeout,
    )
    adapter = PygameJoystickAdapter(config)
    show(PendantController(config, client, adapter))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
