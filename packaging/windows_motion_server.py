from windows_runtime import prepare_runtime
import sys


root = prepare_runtime()

from configuration import ConfigurationSource
from motion_server.application import MotionServerApplication


if __name__ == "__main__":
    if sys.argv[1:2] == ["parameter-store"]:
        from device.virtual_device.parameter_store.__main__ import main as store_main
        sys.exit(store_main(sys.argv[2:]))
    sys.exit(MotionServerApplication.from_source(
        ConfigurationSource(
            project_root=root,
            project_filename="config.txt",
            device_filename="config.txt",
        ),
        argv=sys.argv[1:],
    ).run())
