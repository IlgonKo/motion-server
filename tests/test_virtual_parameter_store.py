import io
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stdout, closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from configuration.builder import build_virtual_parameter_store
from configuration.models import BackendType, CmmtDeviceConfig
from device.cmmt.non_pdo_configuration import CMMT_NON_PDO_CONFIGURATIONS
from device.cmmt.profile import CMMTASDeviceProfile, CMMTSTDeviceProfile
from device.virtual_device.parameter_store import ParameterStore, StoreWorker, StoreLock, StoreError
from device.virtual_device.parameter_store.__main__ import main as cli
from device.virtual_servo_drive.servo_model import VirtualCiA402Servo
from ethercat.mock_master import MockMaster
from ethercat.mock_slave import MockSlave
from motion_server.api.deferred import DeferredResponse
from motion_server.app.client_transport import process_pending_responses
from motion_server.failure import OperationConflictException


def profile(cls=CMMTASDeviceProfile):
    return cls(axis_index=0, slave_index=0, device_config=CmmtDeviceConfig(
        profile_name=cls.name, axis_index=0, pdo_configuration='motion_server_default',
        non_pdo_configuration=CMMT_NON_PDO_CONFIGURATIONS['linear_mm']))


class VirtualParameterStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'parameters.sqlite'

    def worker(self):
        worker = StoreWorker(self.path)
        self.addCleanup(worker.close)
        return worker

    def servo(self, worker, cls=CMMTASDeviceProfile):
        return VirtualCiA402Servo(device_profile=profile(cls), parameter_store=worker, storage_id='axis_x')

    def save(self, servo):
        servo.od.write_role('parameter_save_command', 1)
        servo.model_update()
        future = servo._save_future
        if future is not None:
            future.result(timeout=3)
            servo.model_update()
        self.assertEqual(servo.od.read_role('parameter_save_return_code'), 0)
        servo.od.write_role('parameter_save_command', 0)
        servo.model_update()

    def test_restore_twenty_values_but_not_pdo_or_runtime_state(self):
        worker = self.worker()
        servo = self.servo(worker)
        servo.od.write(0x6083, 2345)
        servo.od.write(0x6081, 1234)
        self.save(servo)
        saved = worker.load('axis_x')
        self.assertEqual(len(saved[2]), 20)
        self.assertNotIn(('ethercat_od', 0x6081, 0), [a for a, _, _ in saved[2]])
        restored = self.servo(worker)
        self.assertEqual(restored.od.read(0x6083), 2345)
        self.assertEqual(restored.od.read(0x6081), 0)
        servo.od.write(0x6083, 4567)
        servo.od.write_role('device_reset_command', 1)
        servo.model_update()
        self.assertEqual(servo.od.read(0x6083), 2345)

    def test_st_profile_uses_same_persistence_contract(self):
        worker = self.worker()
        servo = self.servo(worker, CMMTSTDeviceProfile)
        servo.od.write(0x6084, 2222)
        self.save(servo)
        self.assertEqual(self.servo(worker, CMMTSTDeviceProfile).od.read(0x6084), 2222)
        with self.assertRaises(StoreError):
            self.servo(worker)

    def test_worker_delay_does_not_block_model_update_or_report_early_success(self):
        worker = self.worker()
        servo = self.servo(worker)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = ParameterStore.save
        def delayed(store, *args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test failed to release writer')
            return original(store, *args)
        with patch.object(ParameterStore, 'save', delayed):
            servo.od.write(0x6083, 2222)
            servo.od.write_role('parameter_save_command', 1)
            servo.model_update()
            self.assertTrue(entered.wait(2))
            for _ in range(100):
                servo.model_update()
            self.assertFalse(servo._save_future.done())
            self.assertEqual(servo.od.read_role('parameter_save_status'), 1)
            self.assertEqual(servo.od.read_role('parameter_save_return_value'), 0)
            # The snapshot is isolated from changes made while it is pending.
            servo.od.write(0x6083, 3333)
            release.set()
            servo._save_future.result(timeout=3)
            servo.model_update()
        self.assertEqual(servo.od.read_role('parameter_save_status'), 0)
        self.assertEqual(servo.od.read(0x6083), 3333)
        self.assertEqual(self.servo(worker).od.read(0x6083), 2222)

    def test_failure_keeps_current_values_and_previous_snapshot(self):
        worker = self.worker()
        servo = self.servo(worker)
        self.save(servo)
        before = worker.load('axis_x')
        servo.od.write(0x6083, 3333)
        with patch.object(ParameterStore, 'save', side_effect=sqlite3.OperationalError('disk full')):
            servo.od.write_role('parameter_save_command', 1)
            servo.model_update()
            with self.assertRaises(sqlite3.OperationalError):
                servo._save_future.result(timeout=3)
            servo.model_update()
        self.assertEqual(servo.od.read_role('parameter_save_return_code'), 1)
        self.assertEqual(servo.od.read(0x6083), 3333)
        self.assertEqual(worker.load('axis_x'), before)

    def test_cli_reset_is_offline_retains_history_and_next_start_uses_preset(self):
        worker = self.worker()
        servo = self.servo(worker)
        servo.od.write(0x6083, 2222)
        self.save(servo)
        self.save(servo)  # Identical values must not create another revision.
        args = ['--path', str(self.path), '--json']
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli(args + ['history', '--storage-id', 'axis_x']), 0)
        self.assertEqual(len(json.loads(output.getvalue())), 1)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli(args + ['factory-reset', '--storage-id', 'axis_x']), 1)
        worker.close()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli(args + ['factory-reset', '--storage-id', 'axis_x']), 0)
            self.assertEqual(cli(args + ['show', '--storage-id', 'axis_x', '--revision', '1']), 0)
        new_worker = self.worker()
        self.assertEqual(self.servo(new_worker).od.read(0x6083), 1000)
        self.assertIsNone(new_worker.load('axis_x'))

    def test_transaction_failure_rolls_back_partial_snapshot_and_revision(self):
        store = ParameterStore(self.path)
        self.addCleanup(store.close)
        values = ((('ethercat_od', 1, 0), 'uint8', b'\x01'),)
        store.save('a', 'profile', 1, values)
        store.db.execute("CREATE TRIGGER fail_value BEFORE INSERT ON snapshot_values BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            store.save('a', 'profile', 1, ((('ethercat_od', 1, 0), 'uint8', b'\x02'),))
        self.assertEqual(store.load('a')[2], values)
        self.assertEqual(store.db.execute('SELECT count(*) FROM snapshots').fetchone()[0], 1)

    def test_corrupt_snapshot_and_version_or_missing_entry_rejected(self):
        worker = self.worker()
        self.save(self.servo(worker))
        saved = worker.load('axis_x')
        worker.close()
        for kind in ('corrupt', 'missing', 'version'):
            with self.subTest(kind=kind):
                store = ParameterStore(self.path)
                if kind == 'corrupt':
                    store.db.execute("UPDATE snapshot_values SET raw=X'00'")
                    store.db.commit()
                    with self.assertRaises(StoreError):
                        store.load('axis_x')
                    store.db.execute('DELETE FROM snapshot_values')
                    store.db.execute('DELETE FROM devices')
                    store.db.execute('DELETE FROM snapshots')
                    store.db.commit()
                else:
                    store.save('axis_x', saved[0], saved[1] + (kind == 'version'),
                               saved[2][:-1] if kind == 'missing' else saved[2])
                store.close()
                if kind != 'corrupt':
                    reopened = StoreWorker(self.path)
                    try:
                        with self.assertRaises(StoreError):
                            self.servo(reopened)
                    finally:
                        reopened.close()

    def test_disabled_store_reports_failure_without_creating_file(self):
        servo = self.servo(None)
        servo.od.write_role('parameter_save_command', 1)
        servo.model_update()
        self.assertEqual(servo.od.read_role('parameter_save_return_code'), 1)
        self.assertFalse(self.path.exists())

    def test_configuration_validation_and_relative_main_file_path(self):
        prefix = 'MOTION_SERVER_VIRTUAL_DEVICE_'
        values = {prefix+'PARAMETER_STORE_ENABLED': '1', prefix+'PARAMETER_STORE_PATH':'data/p.sqlite',
                  prefix+'STORAGE_IDS':'0:axis_x'}
        source = SimpleNamespace(values=values, main_config_directory=Path(self.temp.name), project_root=Path('/unused'))
        devices = [SimpleNamespace(slave_index=0, device=CmmtDeviceConfig('cmmt_as', 0, 'motion_server_default'))]
        result = build_virtual_parameter_store(source, devices, BackendType.MOCK)
        self.assertEqual(result.path, (Path(self.temp.name)/'data/p.sqlite').resolve())
        for ids in ('', '0:a,0:b', '0:a,1:a', '1:a', '0:Bad Name'):
            with self.subTest(ids=ids):
                values[prefix+'STORAGE_IDS'] = ids
                with self.assertRaises(ValueError):
                    build_virtual_parameter_store(source, devices, BackendType.MOCK)

    def test_save_response_waits_while_pdo_continues_and_keeps_request_id(self):
        worker = self.worker()
        servo = self.servo(worker)
        master = MockMaster([MockSlave(servo, servo.device_profile.pdo_configuration)],
                            device_profiles=[servo.device_profile])
        master.connect(target_state='preop')
        master.enter_operational()
        self.addCleanup(master.close)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = ParameterStore.save
        def delayed(store, *args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test did not release writer')
            return original(store, *args)
        client = {'output_buffer': bytearray()}
        with patch.object(ParameterStore, 'save', delayed):
            pending = servo.device_profile.save_parameters(master, 0, asynchronous=True)
            self.assertTrue(entered.wait(2))
            with self.assertRaises(OperationConflictException):
                servo.device_profile.save_parameters(master, 0, asynchronous=True)
            message = {'cmd': 'system/axis/param_save', 'axis': 0, 'request_id': 'save-123'}
            client['pending_responses'] = [(message, DeferredResponse(pending.poll, pending.cancel), master)]
            for _ in range(100):
                master.prepare_processdata()
                master.send_processdata()
                master.receive_processdata()
                process_pending_responses(client, master)
            self.assertEqual(client['output_buffer'], b'')
            self.assertEqual(master.wkc, master.expected_wkc())
            release.set()
            servo._save_future.result(timeout=3)
            servo.model_update()
            process_pending_responses(client, master)
        response = json.loads(client['output_buffer'])
        self.assertEqual(response['request_id'], 'save-123')
        self.assertEqual(response['result'], 'success')
        self.assertFalse(client['pending_responses'])

    def test_lost_runtime_returns_failure_not_success(self):
        from unittest.mock import Mock
        pending = DeferredResponse(Mock(return_value={'saved': True}), Mock())
        owner = SimpleNamespace(transport_available=lambda: True)
        client = {'output_buffer': bytearray(), 'pending_responses': [
            ({'cmd': 'system/axis/param_save', 'request_id': 'old'}, pending, owner)]}
        process_pending_responses(client, None)
        self.assertEqual(json.loads(client['output_buffer'])['result'], 'fail')
        pending.poll.assert_not_called()
        pending.cancel.assert_called_once()

    def test_shutdown_drains_worker_and_bus_close_keeps_ownership(self):
        from motion_server.app.runtime import AxisRuntime
        from motion_server.app.startup import close_initialization_resource
        from unittest.mock import Mock
        worker = self.worker()
        runtime = object.__new__(AxisRuntime)
        runtime.device_manager = Mock()
        runtime.parameter_store = worker
        runtime.close()
        with self.assertRaises(StoreError):
            StoreLock(self.path)
        self.save(self.servo(worker))
        close_initialization_resource(runtime)
        close_initialization_resource(runtime.parameter_store)
        with StoreLock(self.path):
            pass

    def test_configuration_runtime_creation_restores_by_id(self):
        from configuration import ConfigurationSource
        from motion_server.application import MotionServerApplication
        from motion_server.app.startup import create_axis_runtime, close_initialization_resource
        folder = Path(self.temp.name)
        (folder / '.env').write_text('''MOTION_SERVER_BACKEND=mock
MOTION_SERVER_BUS=0:axis:cmmt-as
MOTION_SERVER_CMMT_SLAVE_NON_PDO_CONFIGURATIONS=0:linear_mm
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_ENABLED=1
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH=parameters.sqlite
MOTION_SERVER_VIRTUAL_DEVICE_STORAGE_IDS=0:axis_x
''')
        app = MotionServerApplication.from_source(ConfigurationSource(project_root=folder), environ={})
        self.assertIsNotNone(app.config, app.initialization_exception)
        config = app.config
        for revision in range(2):
            runtime = create_axis_runtime(config.ethercat, config.motion, config.logging,
                config.devices, parameter_store_config=config.virtual_parameter_store)
            try:
                servo = runtime.ethercat_master.virtual_device(0)
                if revision == 0:
                    servo.od.write(0x6083, 2121)
                    self.save(servo)
                else:
                    self.assertEqual(servo.od.read(0x6083), 2121)
            finally:
                close_initialization_resource(runtime)
                close_initialization_resource(runtime.parameter_store)

    def test_schema_damage_does_not_silently_recreate_missing_tables(self):
        worker = self.worker()
        worker.close()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE devices')
        with self.assertRaises(StoreError):
            StoreWorker(self.path)
        with StoreLock(self.path):
            pass

    def test_existing_empty_file_is_rejected_without_reinitialization(self):
        self.path.write_bytes(b'')
        with self.assertRaises(StoreError):
            StoreWorker(self.path)
        self.assertEqual(self.path.read_bytes(), b'')
        with StoreLock(self.path):
            pass

    def test_truncated_saved_database_is_not_treated_as_first_start(self):
        worker = self.worker()
        self.save(self.servo(worker))
        worker.close()
        self.path.write_bytes(b'')
        with self.assertRaises(StoreError):
            StoreWorker(self.path)
        self.assertEqual(self.path.read_bytes(), b'')

    def test_orphan_history_rejects_restore_and_save_without_changing_history(self):
        worker = self.worker()
        self.save(self.servo(worker))
        saved = worker.load('axis_x')
        worker.close()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("DELETE FROM devices WHERE id='axis_x'")
            db.commit()
            before = db.execute('SELECT * FROM snapshots').fetchall()
        reopened = self.worker()
        with self.assertRaisesRegex(StoreError, 'without an active device record'):
            self.servo(reopened)
        with self.assertRaises(StoreError):
            reopened.save('axis_x', *saved).result(timeout=3)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT * FROM snapshots').fetchall(), before)
            self.assertEqual(db.execute('SELECT count(*) FROM devices').fetchone()[0], 0)

    def test_unused_storage_id_in_valid_database_still_uses_defaults(self):
        worker = self.worker()
        self.save(self.servo(worker))
        other = VirtualCiA402Servo(device_profile=profile(), parameter_store=worker,
                                  storage_id='new_axis')
        self.assertEqual(other.od.read(0x6083), 1000)
        self.assertIsNone(worker.load('new_axis'))

    def test_generic_address_families_and_order_independent_no_change(self):
        store = ParameterStore(self.path)
        self.addCleanup(store.close)
        values = ((('ethercat_od', 0x2000, 1), 'uint8', b'\x00'),
                  (('ap_parameter', 2, 246, 0), 'uint16', b'\x01\x00'),
                  (('io_link_isdu', 3, 1, 81, 0), 'uint8', b'\x02'))
        self.assertEqual(store.save('remote_io', 'future_virtual_cpx', 1, values), 1)
        self.assertEqual(store.save('remote_io', 'future_virtual_cpx', 1, reversed(values)), 1)
        self.assertEqual(set(store.load('remote_io')[2]), set(values))

    def test_cli_entry_does_not_initialize_server(self):
        from motion_server.__main__ import main
        with patch('motion_server.__main__.MotionServerApplication.from_source') as startup:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['parameter-store', '--path', str(self.path), 'list']), 1)
            startup.assert_not_called()

    def test_queue_is_bounded_and_rejects_without_waiting(self):
        worker = self.worker()
        release = threading.Event()
        self.addCleanup(release.set)
        original = ParameterStore.save
        def delayed(store, *args):
            if not release.wait(3):
                raise RuntimeError('test did not release writer')
            return original(store, *args)
        with patch.object(ParameterStore, 'save', delayed):
            futures = [worker.save(str(i), 'test', 1, ()) for i in range(16)]
            with self.assertRaises(StoreError):
                worker.save('overflow', 'test', 1, ())
            release.set()
            for future in futures:
                future.result(timeout=3)

    def test_factory_reset_failure_preserves_active_revision(self):
        store = ParameterStore(self.path)
        self.addCleanup(store.close)
        values = ((('ethercat_od', 1, 0), 'uint8', b'\x01'),)
        store.save('a', 'test', 1, values)
        store.db.execute("CREATE TRIGGER fail_reset BEFORE UPDATE ON devices BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            store.factory_reset('a')
        self.assertEqual(store.load('a')[2], values)
        self.assertEqual(store.db.execute('SELECT count(*) FROM snapshots').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
