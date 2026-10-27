"""Deterministic fault injection in a fake client; no socket or hardware access."""
import copy
import json
from pathlib import Path
import queue
import threading
import time
import unittest

from sequence import Feedback, inputs_met, motion_met, run, validate

CONFIG = json.loads((Path(__file__).parent / 'settings.json').read_text())


class FakeClient:
    def __init__(self, mode='', cancel=None):
        self.mode, self.cancel = mode, cancel
        self.is_connected = False
        self.owned = False
        self.q = queue.Queue()
        self.done = threading.Event()
        self.requests = []
        self.moves = 0
        self.positions = [0., 0., 0.]
        self.outputs = [False, 0]
        self.injected = False

    def snapshot(self):
        return {'process_data_valid': True, 'statuswords': [33831]*3,
                'actual_positions': self.positions[:], 'target_positions': self.positions[:],
                'command_authority': {'owned_by_this_client': self.owned},
                'server_health': {'fault_count': 0},
                'io': {'devices': [{'id': 'io0', 'modules': [
                    {'slot': 1, 'outputs': {'digital': [self.outputs[0]]}},
                    {'slot': 2, 'outputs': {'analog': [self.outputs[1]]}},
                    {'slot': 3, 'inputs': {'digital': [self.mode != 'input_timeout']}},
                    {'slot': 4, 'inputs': {'analog': [100]}}]}]}}

    def start(self):
        self.is_connected = True
        def produce():
            while not self.done.wait(0.015):
                f = self.snapshot()
                if self.moves and self.mode == 'feedback_timeout':
                    continue
                if self.moves and self.mode == 'invalid':
                    f['process_data_valid'] = False
                if self.moves and self.mode == 'missing':
                    f['statuswords'] = [33831]
                if self.moves and self.mode == 'one_axis':
                    f['statuswords'][2] |= 256
                if self.moves and self.mode == 'fault':
                    f['statuswords'][2] |= 8
                if self.moves and self.mode == 'authority_loss':
                    self.owned = False
                    f['command_authority']['owned_by_this_client'] = False
                if self.moves and self.mode == 'connection_loss':
                    self.is_connected = False
                    continue
                self.q.put(f)
        self.thread = threading.Thread(target=produce, daemon=True)
        self.thread.start()

    def stop(self):
        self.done.set()
        self.thread.join(1)
        self.is_connected = False

    def wait_connected(self, timeout):
        return self.is_connected

    def get_feedback(self, timeout):
        return self.q.get(timeout=timeout)

    def request(self, message, timeout):
        self.requests.append(copy.deepcopy(message))
        cmd = message['cmd']
        data = {}
        if cmd == 'system/axis/status':
            data = {'axis_metadata': CONFIG['units']}
        elif cmd == 'system/authority/request':
            self.owned = True
            if self.mode == 'authority_timeout':
                raise TimeoutError('Injected response timeout after authority grant')
            data = {'owned_by_this_client': True, 'granted': True}
        elif cmd == 'system/authority/status':
            data = {'owned_by_this_client': self.owned}
        elif cmd == 'system/authority/release':
            self.owned = False
            data = {'owned_by_this_client': False}
        elif cmd == 'system/axes/move_abs':
            self.moves += 1
            self.positions = message['positions'][:]
            if self.mode in ('fail', 'response_timeout'):
                if self.mode == 'response_timeout':
                    raise TimeoutError('Injected request timeout: execution unknown')
                return {'result': 'fail', 'failure': {'code': 'TEST_FAIL', 'message': 'Injected', 'details': {'axis': 2}}}
            if self.mode == 'cancel':
                self.cancel.set()
        elif cmd == 'system/io/output_write':
            self.outputs[0 if message['kind'] == 'digital' else 1] = message['value']
            if self.mode == 'grip_partial_fail' and message['kind'] == 'analog':
                return {'result': 'fail', 'failure': {'code': 'OUTPUT_FAIL', 'message': 'Injected'}}
        elif cmd == 'system/axes/stop':
            if self.mode == 'stop_fail':
                return {'result': 'fail', 'failure': {'code': 'STOP_FAIL', 'message': 'Injected'}}
            if self.mode == 'cancel_cleanup':
                self.cancel.set()
        return {'result': 'success', 'data': data}


class SequenceTests(unittest.TestCase):
    def execute(self, mode=''):
        c = copy.deepcopy(CONFIG)
        c.update(request_timeout=0.3, move_timeout=0.15, input_timeout=0.15, feedback_timeout=0.12)
        cancel = threading.Event()
        client = FakeClient(mode, cancel)
        result = run(client, c, cancel, log=lambda _: None)
        return client, result

    def test_normal_order_and_payloads(self):
        client, result = self.execute()
        self.assertEqual(result['state'], 'completed', result)
        commands = [r for r in client.requests if r['cmd'] in ('system/axis/profile', 'system/axes/move_abs', 'system/io/output_write', 'system/axes/stop')]
        self.assertEqual([r['cmd'] for r in commands], ['system/axis/profile']*3 +
                         ['system/axes/move_abs'] + ['system/io/output_write']*2 +
                         ['system/axes/move_abs'] + ['system/io/output_write']*2 + ['system/axes/stop'])
        for r in commands[:3]:
            self.assertEqual(r['profile_acceleration'], 100.)
            self.assertEqual(r['profile_deceleration'], 100.)
            self.assertNotIn('profile_velocity', r)
        for r in commands:
            if r['cmd'].endswith('move_abs'):
                self.assertEqual(r['profile_velocities'], [5.,5.,2.])
                self.assertNotIn('velocities', r)
        self.assertEqual(client.outputs, [False, 0])
        self.assertTrue(result['cleanup_complete'])
        self.assertTrue(result['authority_released'])

    def test_failures_never_enter_place_or_release(self):
        for mode in ('fail', 'response_timeout', 'input_timeout', 'feedback_timeout',
                     'invalid', 'missing', 'one_axis', 'fault', 'connection_loss',
                     'authority_loss', 'cancel', 'grip_partial_fail'):
            with self.subTest(mode=mode):
                client, result = self.execute(mode)
                self.assertIn(result['state'], ('failed', 'cancelled'), result)
                self.assertEqual(client.moves, 1)
                writes = [r for r in client.requests if r['cmd'] == 'system/io/output_write']
                self.assertTrue(all(r['value'] in (True, 100) for r in writes))
                self.assertEqual(sum(r['cmd'] == 'system/authority/request' for r in client.requests), 1)
                if mode in ('authority_loss', 'connection_loss'):
                    self.assertFalse(result['cleanup_complete'])
                    self.assertIn('INCOMPLETE', result['cleanup_error'])
                else:
                    self.assertEqual(sum(r['cmd'] == 'system/axes/stop' for r in client.requests), 1)
                if mode in ('input_timeout', 'grip_partial_fail'):
                    self.assertEqual(client.outputs, [True, 100])

    def test_cleanup_fail_and_cancel(self):
        for mode in ('stop_fail', 'cancel_cleanup'):
            with self.subTest(mode=mode):
                _, result = self.execute(mode)
                self.assertNotEqual(result['state'], 'completed')

    def test_authority_response_timeout_cleanup(self):
        client, result = self.execute('authority_timeout')
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(client.moves, 0)
        self.assertTrue(result['cleanup_complete'])
        self.assertTrue(result['authority_released'])

    def test_all_axes_and_inputs(self):
        client = FakeClient()
        f = client.snapshot()
        self.assertTrue(motion_met(f, [0,1,2], [0,0,0]))
        f['statuswords'][2] |= 256
        self.assertFalse(motion_met(f, [0,1,2], [0,0,0]))
        f['statuswords'][2] = 0
        self.assertFalse(motion_met(f, [0,1,2], [0,0,0]))
        self.assertTrue(inputs_met(f, CONFIG['grip_inputs']))
        f['io']['devices'][0]['modules'][3]['inputs']['analog'][0] = 49
        self.assertFalse(inputs_met(f, CONFIG['grip_inputs']))
        f['io']['devices'][0]['modules'].pop()
        self.assertFalse(inputs_met(f, CONFIG['grip_inputs']))

    def test_old_queue_cannot_complete_and_loss_latches(self):
        c = copy.deepcopy(CONFIG)
        c['feedback_timeout'] = 0.1
        client = FakeClient()
        client.is_connected = client.owned = True
        fb = Feedback(client, c)
        for _ in range(20):
            client.q.put(client.snapshot())
        fb.thread.start()
        try:
            after = fb.mark()
            with self.assertRaises(TimeoutError):
                fb.wait(lambda _: True, after, 0.05, threading.Event())
            f = client.snapshot()
            f['command_authority']['owned_by_this_client'] = False
            client.q.put(f)
            client.q.put(client.snapshot())
            fb.mark()
            with self.assertRaisesRegex(RuntimeError, 'authority lost'):
                fb.check(threading.Event())
        finally:
            fb.done.set()
            fb.thread.join(1)

    def test_invalid_configuration(self):
        for key, value in (('acceleration', True), ('move_timeout', float('nan')), ('host', 'other')):
            c = copy.deepcopy(CONFIG)
            c[key] = value
            with self.assertRaises(ValueError):
                validate(c)

    def test_requests_match_schema_fields(self):
        client, _ = self.execute()
        definitions = {}
        for name in ('axis', 'io', 'system'):
            schema = json.loads((Path(__file__).parent.parent / 'motion_server/api/schema' / (name+'.json')).read_text())
            for definition in schema['$defs'].values():
                cmd = definition.get('properties', {}).get('cmd', {}).get('const')
                if cmd:
                    definitions[cmd] = definition
        for request in client.requests:
            definition = definitions[request['cmd']]
            self.assertTrue(set(request) <= set(definition['properties']))
            self.assertTrue(set(definition['required']) <= set(request))
            for key, value in request.items():
                if key in ('axis', 'slot', 'channel'):
                    self.assertIs(type(value), int)
            if request['cmd'] == 'system/io/output_write':
                self.assertIs(type(request['value']), bool if request['kind'] == 'digital' else int)


if __name__ == '__main__':
    unittest.main(verbosity=2)
