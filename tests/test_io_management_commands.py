import unittest
from types import SimpleNamespace

from device.capabilities import DeviceCapability, validate_device_capabilities
from device.cpx_ap_i_ec.profile import CPXApIEcDeviceProfile
from motion_server.failure import InvalidArgumentException, UnsupportedOperationException
from motion_server.handlers.command.io_management import (
    reset_io_device,
    restart_io_device,
    set_io_parameter_storage,
)


class RecordingSdo:
    def __init__(self):
        self.writes = []

    def write_uint8(self, slave_index, index, subindex, value):
        self.writes.append((slave_index, index, subindex, value))


class RecordingMaster:
    def __init__(self):
        self.sdo = RecordingSdo()


class FakeIoGroup:
    def __init__(self, profile, ethercat_master=None):
        self.slave = SimpleNamespace(device_profile=profile)
        if ethercat_master is not None:
            self.ethercat_master = ethercat_master

    def slave_index(self, io_selector):
        if io_selector != "io0":
            raise ValueError(f"Unknown I/O device: {io_selector}")
        return 4

    def selected_device(self, io_id=None, slave_index=None):
        if slave_index != 4:
            raise ValueError(f"Unknown I/O device: {slave_index}")
        return {
            "id": "io0",
            "slave_index": 4,
            "profile": getattr(self.slave.device_profile, "name", ""),
            "slave": self.slave,
        }


def runtime(profile, ethercat_master=None):
    active_runtime = RecordingMaster()
    active_runtime.device_manager = SimpleNamespace(
        io=FakeIoGroup(profile, ethercat_master=ethercat_master)
    )
    return active_runtime


class UnsupportedCpxProfile:
    name = "cpx_ap_i_ec"
    capabilities = frozenset()


class ParameterStorageIoProfile:
    name = "parameter_storage_io"
    capabilities = frozenset({DeviceCapability.IO_PARAMETER_STORAGE})

    def set_io_parameter_storage(self, master, slave_index, mode):
        return {"slave_index": slave_index, "storage": mode}


class RestartingIoProfile:
    name = "restarting_io"
    capabilities = frozenset({
        DeviceCapability.IO_RESET,
        DeviceCapability.IO_RESTART,
    })

    def reset_io_device(self, master, slave_index):
        return {"slave_index": slave_index, "reset": True}

    def restart_io_device(self, master, slave_index):
        return {"slave_index": slave_index, "restarted": True}


class IoManagementCommandTest(unittest.TestCase):
    def test_cpx_parameter_storage_writes_non_volatile_mode(self):
        profile = CPXApIEcDeviceProfile.__new__(CPXApIEcDeviceProfile)
        master = RecordingMaster()

        result = profile.set_io_parameter_storage(master, 4, "non_volatile")

        self.assertEqual(master.sdo.writes, [(4, 0x27F1, 0x01, 1)])
        self.assertEqual(
            result,
            {"object": "0x27F1:01", "mode": 1, "storage": "non_volatile"},
        )

    def test_cpx_parameter_storage_writes_volatile_mode(self):
        profile = CPXApIEcDeviceProfile.__new__(CPXApIEcDeviceProfile)
        master = RecordingMaster()

        result = profile.set_io_parameter_storage(master, 4, "volatile")

        self.assertEqual(master.sdo.writes, [(4, 0x27F1, 0x01, 0)])
        self.assertEqual(
            result,
            {"object": "0x27F1:01", "mode": 0, "storage": "volatile"},
        )

    def test_io_param_storage_delegates_to_supported_profile(self):
        data = set_io_parameter_storage(
            {"cmd": "system/io/param_storage", "io": "io0", "mode": "volatile"},
            runtime(ParameterStorageIoProfile()),
            {},
            {"id": 1},
        )

        self.assertEqual(data["io"], "io0")
        self.assertEqual(data["slave_index"], 4)
        self.assertEqual(
            data["result"],
            {"slave_index": 4, "storage": "volatile"},
        )

    def test_io_param_storage_uses_raw_ethercat_master_not_axis_sdo(self):
        raw_master = RecordingMaster()
        active_runtime = runtime(CPXApIEcDeviceProfile.__new__(CPXApIEcDeviceProfile))
        active_runtime.sdo = SimpleNamespace(
            write_uint8=lambda *_args: (_ for _ in ()).throw(
                IndexError("axis sdo should not be used")
            )
        )
        active_runtime.device_manager.io.ethercat_master = raw_master

        data = set_io_parameter_storage(
            {
                "cmd": "system/io/param_storage",
                "io": "io0",
                "mode": "non_volatile",
            },
            active_runtime,
            {},
            {"id": 1},
        )

        self.assertEqual(raw_master.sdo.writes, [(4, 0x27F1, 0x01, 1)])
        self.assertEqual(data["result"]["storage"], "non_volatile")

    def test_io_param_storage_rejects_unknown_mode(self):
        with self.assertRaises(InvalidArgumentException):
            set_io_parameter_storage(
                {"cmd": "system/io/param_storage", "io": "io0", "mode": "factory"},
                runtime(ParameterStorageIoProfile()),
                {},
                {"id": 1},
            )

    def test_cpx_reset_and_restart_are_unsupported_until_profile_declares_support(self):
        active_runtime = runtime(UnsupportedCpxProfile())

        with self.assertRaises(UnsupportedOperationException):
            reset_io_device(
                {"cmd": "system/io/reset", "io": "io0"},
                active_runtime,
                {},
                {"id": 1},
            )
        with self.assertRaises(UnsupportedOperationException):
            restart_io_device(
                {"cmd": "system/io/restart", "io": "io0"},
                active_runtime,
                {},
                {"id": 1},
            )

    def test_reset_and_restart_delegate_to_supported_profile(self):
        active_runtime = runtime(RestartingIoProfile())

        reset_result = reset_io_device(
            {"cmd": "system/io/reset", "io": "io0"},
            active_runtime,
            {},
            {"id": 1},
        )
        restart_result = restart_io_device(
            {"cmd": "system/io/restart", "io": "io0"},
            active_runtime,
            {},
            {"id": 1},
        )

        self.assertTrue(reset_result["result"]["reset"])
        self.assertTrue(restart_result["result"]["restarted"])

    def test_io_capability_contract_requires_profile_methods(self):
        class InvalidProfile:
            name = "invalid"
            capabilities = frozenset({DeviceCapability.IO_PARAMETER_STORAGE})

        with self.assertRaisesRegex(TypeError, "set_io_parameter_storage"):
            validate_device_capabilities(InvalidProfile())


if __name__ == "__main__":
    unittest.main()
