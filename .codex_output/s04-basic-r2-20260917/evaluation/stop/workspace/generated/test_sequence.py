"""Offline tests: no network, no server implementation or evaluation tools."""
from copy import deepcopy
import json
from pathlib import Path
import queue
import threading
import time
import unittest

from sequence import Feedback, Sequence, axes_complete, inputs_match, prepare

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / 'settings.json').read_text(encoding='utf-8'))
BASE = json.loads((HERE / 'initial_feedback.json').read_text(encoding='utf-8'))
BASE['command_authority']['owned_by_this_client'] = True


class Snapshots:
    def __init__(self):
        self.f = deepcopy(BASE)
        self.serial = 1
        self.loss = self.fault = None
        self.monitor = False
        self.frozen = False
        self.received = time.monotonic()

    def barrier(self, timeout): return self.serial

    def snapshot(self):
        if not self.frozen:
            self.serial += 1
            self.received = time.monotonic()
        return self.serial, self.received, deepcopy(self.f), self.loss, self.fault


class FakeClient:
    def __init__(self, feedback, scenario='normal'):
        self.feedback = feedback
        self.scenario = scenario
        self.is_connected = True
        self.commands = []
        self.cancel = None

    def request(self, message, *, timeout):
        self.commands.append(deepcopy(message))
        cmd = message['cmd']
        f = self.feedback.f
        if cmd == 'system/authority/status':
            return {'result': 'success', 'data': {'owned_by_this_client': True}}
        if cmd == 'system/axes/move_abs':
            if self.scenario == 'fail':
                return {'result': 'fail', 'failure': {'code': 'test_failure', 'message': 'rejected', 'details': {'axis': 2}}}
            if self.scenario == 'response_timeout': raise TimeoutError('request timeout; execution uncertain')
            f['actual_positions'] = message['positions'][:]
            f['target_positions'] = message['positions'][:]
            if self.scenario == 'one_axis': f['statuswords'][2] |= 256
            if self.scenario == 'invalid': f['process_data_valid'] = False
            if self.scenario == 'missing_axis': f['statuswords'] = [33831]
            if self.scenario == 'stale': self.feedback.frozen = True
            if self.scenario == 'disconnect':
                self.is_connected = False
                self.feedback.loss = 'Connection lost'
            if self.scenario == 'reconnected': self.feedback.loss = 'Connection lost then reconnected'
            if self.scenario == 'authority': self.feedback.loss = 'Authority lost'
            if self.scenario == 'fault': self.feedback.fault = 'Runtime Fault'
            if self.scenario == 'cancel': self.cancel.set()
        if cmd == 'system/io/output_write' and message['kind'] == 'analog' and message['value'] == 100:
            if self.scenario == 'input_timeout':
                f['io']['devices'][0]['modules'][3]['inputs']['analog'][0] = 49
            if self.scenario == 'output_fail':
                return {'result': 'fail', 'failure': {'code': 'output_failed', 'message': 'test'}}
        if cmd == 'system/axes/stop':
            if self.scenario == 'stop_fail':
                return {'result': 'fail', 'failure': {'code': 'stop_failed', 'message': 'test'}}
            f['statuswords'] = [33831] * 3
            f['process_data_valid'] = True
            self.feedback.frozen = False
        return {'result': 'success', 'data': {}}


class SequenceTests(unittest.TestCase):
    def run_case(self, scenario):
        c = deepcopy(CONFIG)
        c.update(move_timeout=0.045, input_timeout=0.045, feedback_timeout=0.025)
        fb = Snapshots()
        client = FakeClient(fb, scenario)
        logs = []
        seq = Sequence(client, fb, c, report=logs.append)
        client.cancel = seq.cancel
        result = seq.run()
        return result, client, seq, logs

    def test_normal_order_and_schema_contract(self):
        result, client, seq, _ = self.run_case('normal')
        self.assertEqual(result, 'completed')
        self.assertTrue(seq.stop_confirmed)
        self.assertEqual([m['cmd'].split('/')[-1] for m in client.commands],
            ['profile'] * 3 + ['move_abs', 'output_write', 'output_write', 'move_abs',
                            'output_write', 'output_write', 'status', 'stop'])
        self.assertEqual([m['value'] for m in client.commands if 'value' in m], [True, 100, False, 0])
        defs = {}
        for name in ('axis', 'io', 'system'):
            defs.update(json.loads((HERE.parent / f'motion_server/api/schema/{name}.json').read_text())['$defs'])
        for request in client.commands:
            schema = defs[request['cmd'].replace('/', '_')]
            self.assertFalse(set(request) - set(schema['properties']))
            self.assertTrue(set(schema['required']) <= set(request))
            if request['cmd'].endswith('move_abs'):
                self.assertIn('profile_velocities', request)
                self.assertNotIn('velocities', request)
                self.assertNotIn('profile_acceleration', request)
        with self.assertRaises(RuntimeError): seq.run()

    def test_failures_forbid_next_step_and_keep_outputs(self):
        for scenario in ('fail', 'response_timeout', 'one_axis', 'invalid', 'missing_axis', 'stale',
                         'disconnect', 'reconnected', 'authority', 'fault', 'cancel'):
            with self.subTest(scenario=scenario):
                result, client, seq, logs = self.run_case(scenario)
                self.assertNotEqual(result, 'completed')
                self.assertEqual(sum(m['cmd'].endswith('move_abs') for m in client.commands), 1)
                self.assertFalse(any(m['cmd'].endswith('output_write') for m in client.commands))
                if scenario in ('disconnect', 'reconnected', 'authority'):
                    self.assertFalse(seq.stop_confirmed)
                    self.assertFalse(any(m['cmd'].endswith('/stop') for m in client.commands))
                    self.assertTrue(any('INCOMPLETE' in m for m in logs))
                else:
                    self.assertTrue(seq.stop_confirmed)
                if scenario == 'cancel': self.assertEqual(result, 'cancelled')
                if scenario == 'fail': self.assertTrue(any('test_failure' in m and 'details' in m for m in logs))

    def test_grasp_failure_does_not_release_or_place(self):
        for scenario in ('input_timeout', 'output_fail'):
            result, client, _, _ = self.run_case(scenario)
            self.assertEqual(result, 'failed')
            self.assertEqual(sum(m['cmd'].endswith('move_abs') for m in client.commands), 1)
            self.assertEqual([m['value'] for m in client.commands if 'value' in m], [True, 100])

    def test_cleanup_failure_not_completed(self):
        result, _, seq, logs = self.run_case('stop_fail')
        self.assertEqual(result, 'failed')
        self.assertFalse(seq.stop_confirmed)
        self.assertTrue(any('INCOMPLETE' in m for m in logs))

    def test_both_inputs_same_snapshot_and_missing_channel(self):
        f = deepcopy(BASE)
        self.assertTrue(inputs_match(f, CONFIG['grasp_conditions']))
        f['io']['devices'][0]['modules'][2]['inputs']['digital'][0] = False
        self.assertFalse(inputs_match(f, CONFIG['grasp_conditions']))
        f['io']['devices'][0]['modules'][2]['inputs']['digital'][0] = True
        f['io']['devices'][0]['modules'][3]['inputs']['analog'] = []
        self.assertFalse(inputs_match(f, CONFIG['grasp_conditions']))

    def test_old_target_not_accepted_with_large_tolerance(self):
        f = deepcopy(BASE)
        f['actual_positions'] = [0.5, 0.6, 0.7]
        f['target_positions'] = [0.5, 0.6, 0.7]
        self.assertFalse(axes_complete(f, [0, 1, 2], [1.0, 1.1, 1.2]))
        f['target_positions'] = [1.0, 1.1, 1.2]
        f['statuswords'][1] &= ~1024
        self.assertFalse(axes_complete(f, [0, 1, 2], [1.0, 1.1, 1.2]))

    def test_own_settings_types_and_run_snapshot(self):
        c = deepcopy(CONFIG)
        c['grasp_outputs'][1]['value'] = True
        with self.assertRaises(ValueError): prepare(c)
        c = deepcopy(CONFIG)
        seq = Sequence(FakeClient(Snapshots()), Snapshots(), c)
        c['pick']['positions'][0] = 999
        self.assertEqual(seq.c['pick']['positions'][0], 0.5)

    def test_input_wait_rejects_missing_axis_even_with_true_inputs(self):
        fb = Snapshots()
        fb.f['statuswords'] = [33831]
        seq = Sequence(FakeClient(fb), fb, CONFIG)
        with self.assertRaises(TimeoutError):
            seq.wait(lambda f: inputs_match(f, CONFIG['grasp_conditions']), 0, 0.025)

    def test_cleanup_attempts_stop_when_feedback_stale(self):
        fb = Snapshots()
        fb.frozen = True
        fb.received = time.monotonic() - 10
        client = FakeClient(fb)
        seq = Sequence(client, fb, CONFIG, report=lambda _: None)
        self.assertEqual(seq.run(), 'failed')
        self.assertTrue(seq.stop_confirmed)
        self.assertEqual([m['cmd'] for m in client.commands],
            ['system/authority/status', 'system/axes/stop'])


class QueueClient:
    def __init__(self):
        self.is_connected = True
        self.q = queue.Queue()
    def get_feedback(self, timeout): return self.q.get(timeout=timeout)


class FeedbackTests(unittest.TestCase):
    def test_barrier_discards_backlog_and_requires_new_snapshot(self):
        client = QueueClient()
        fb = Feedback(client, [0, 1, 2])
        for _ in range(20): client.q.put(deepcopy(BASE))
        fb.flush.set()  # barrier pending before the sole reader starts
        fb.start()
        try:
            self.assertTrue(fb.flushed.wait(0.5))
            self.assertIsNone(fb.snapshot()[2])
            self.assertEqual(fb.snapshot()[0], 0)
            client.q.put(deepcopy(BASE))
            deadline = time.monotonic() + 0.5
            while fb.snapshot()[0] == 0 and time.monotonic() < deadline: time.sleep(0.005)
            self.assertEqual(fb.snapshot()[0], 1)
        finally: fb.close()

    def test_fault_and_authority_loss_are_latched(self):
        fb = Feedback(QueueClient(), [0, 1, 2])
        fb.monitor = True
        f = deepcopy(BASE)
        f['statuswords'][2] |= 8
        fb._accept(f)
        f['statuswords'][2] &= ~8
        f['command_authority']['owned_by_this_client'] = False
        fb._accept(f)
        fb._accept(deepcopy(BASE))
        self.assertEqual(fb.snapshot()[3:], ('Authority lost', 'Runtime Fault'))


if __name__ == '__main__': unittest.main(verbosity=2)
