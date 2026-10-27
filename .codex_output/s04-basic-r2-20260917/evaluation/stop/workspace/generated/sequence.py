"""One run of the user's sequence. All API calls use the official request directly."""
from copy import deepcopy
import json
import math
import queue
import threading
import time


class Cancelled(Exception):
    pass


def success(response):
    if response.get('result') != 'success':
        raise RuntimeError('API Fail: ' + json.dumps(response, ensure_ascii=False))
    return response['data']


def prepare(config):
    c = deepcopy(config)  # immutable Run snapshot, independent of caller edits
    axes = list(c['roles'].values())
    if len(axes) != 3 or len(set(axes)) != 3 or any(type(a) is not int or a < 0 for a in axes):
        raise ValueError('Three distinct nonnegative axis indices required')
    def number(v, positive=False):
        if type(v) not in (int, float) or not math.isfinite(v) or (positive and v <= 0):
            raise ValueError(f'Invalid numeric setting: {v!r}')
    for key in ('request_timeout', 'move_timeout', 'input_timeout', 'feedback_timeout', 'position_tolerance', 'velocity_tolerance'):
        number(c[key], True)
    for key in ('acceleration', 'deceleration'):
        if len(c[key]) != 3: raise ValueError(key)
        for v in c[key]: number(v, True)
    for name in ('pick', 'place'):
        for key in ('positions', 'profile_velocities'):
            if len(c[name][key]) != 3: raise ValueError(name + '.' + key)
            for v in c[name][key]: number(v, key == 'profile_velocities')
    for key in ('grasp_outputs', 'release_outputs', 'grasp_conditions', 'release_conditions'):
        for item in c[key]:
            if not isinstance(item['io'], str) or not item['io']: raise ValueError('io')
            for field in ('slot', 'channel'):
                if type(item[field]) is not int or item[field] < 0: raise ValueError(field)
            if item['kind'] not in ('digital', 'analog'): raise ValueError('kind')
            if type(item['value']) is not (bool if item['kind'] == 'digital' else int):
                raise ValueError('Digital requires bool; analog requires raw int')
            if 'conditions' in key and item['op'] not in ('eq', 'ge', 'le'): raise ValueError('op')
    return c


def inputs_match(f, conditions):
    try:
        for c in conditions:
            device = next(d for d in f['io']['devices'] if d['id'] == c['io'])
            module = next(m for m in device['modules'] if m['slot'] == c['slot'])
            v = module['inputs'][c['kind']][c['channel']]
            if type(v) is not type(c['value']): return False
            if not {'eq': v == c['value'], 'ge': v >= c['value'], 'le': v <= c['value']}[c['op']]: return False
        return True
    except (KeyError, IndexError, StopIteration, TypeError):
        return False


def axes_complete(f, axes, positions=None, tolerance=0.5):
    try:
        for i, a in enumerate(axes):
            sw = f['statuswords'][a]
            if sw & 256: return False
            if positions is not None:
                if not sw & 1024: return False
                if not abs(f['actual_positions'][a] - positions[i]) <= tolerance: return False
                # Target equality prevents old adjacent goals passing the broad position tolerance.
                if not math.isclose(f['target_positions'][a], positions[i], abs_tol=1e-9, rel_tol=0): return False
        return True
    except (KeyError, IndexError, TypeError):
        return False


class Feedback:
    """The sole queue consumer; latch losses/faults even during blocking requests."""
    def __init__(self, client, axes):
        self.client, self.axes = client, axes
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.flush = threading.Event()
        self.flushed = threading.Event()
        self.latest = None
        self.serial = 0
        self.received = 0.0
        self.loss = None
        self.fault = None
        self.monitor = False
        self.seen_connection = False
        self.seen_owner = False
        self.thread = threading.Thread(target=self._read, daemon=True)

    def start(self): self.thread.start()

    def close(self):
        self.done.set()
        self.thread.join(timeout=1)

    def _accept(self, value, publish=True):
        with self.lock:
            owner = value.get('command_authority', {}).get('owned_by_this_client', False)
            if self.seen_owner and not owner: self.loss = 'Authority lost'
            self.seen_owner |= owner
            if self.monitor and value.get('process_data_valid'):
                if value.get('server_health', {}).get('fault_count', 0) or any(
                    value.get('statuswords', [])[a] & 8 for a in self.axes
                    if a < len(value.get('statuswords', []))
                ): self.fault = 'Runtime Fault'
            if publish and not self.loss:
                self.serial += 1
                self.received = time.monotonic()
                self.latest = value

    def _read(self):
        while not self.done.is_set():
            if self.client.is_connected:
                self.seen_connection = True
            elif self.seen_connection:
                with self.lock:
                    self.loss = 'Connection lost; no resume after reconnect'
                    self.latest = None
            if self.flush.is_set():
                # Only this thread drains old queue entries. Never publish them as fresh.
                while True:
                    try: self._accept(self.client.get_feedback(timeout=0), publish=False)
                    except queue.Empty: break
                with self.lock: self.latest = None
                self.flush.clear()
                self.flushed.set()
            try: value = self.client.get_feedback(timeout=0.01)
            except queue.Empty: continue
            if self.client.is_connected: self._accept(value)

    def barrier(self, timeout):
        self.flushed.clear()
        self.flush.set()
        if not self.flushed.wait(timeout): raise TimeoutError('Feedback consumer timeout')
        with self.lock: return self.serial

    def snapshot(self):
        with self.lock:
            return self.serial, self.received, deepcopy(self.latest), self.loss, self.fault


class Sequence:
    def __init__(self, client, feedback, config, cancel=None, report=print):
        self.client, self.feedback = client, feedback
        self.c = prepare(config)
        self.axes = list(self.c['roles'].values())
        self.cancel = cancel if cancel is not None else threading.Event()
        self.report = report
        self.state = 'idle'
        self.step = 'idle'
        self.stop_confirmed = False
        self.run_lock = threading.Lock()
        self.evidence = {}

    def checkpoint(self, cleanup=False):
        if self.cancel.is_set() and not cleanup: raise Cancelled('Stop/Ctrl+C requested')
        serial, received, f, loss, fault = self.feedback.snapshot()
        if not self.client.is_connected or loss: raise RuntimeError(loss or 'Connection lost')
        if not cleanup and fault: raise RuntimeError(fault)
        if f and not f.get('command_authority', {}).get('owned_by_this_client'):
            raise RuntimeError('Authority not owned')
        if not cleanup and time.monotonic() - received > self.c['feedback_timeout']:
            raise TimeoutError('Feedback timeout')
        return serial, f

    def wait(self, predicate, after, timeout, cleanup=False):
        deadline = time.monotonic() + timeout
        last_fresh = time.monotonic()
        seen = after
        while time.monotonic() < deadline:
            serial, f = self.checkpoint(cleanup)
            if serial > seen:
                seen = serial
                last_fresh = time.monotonic()
            if time.monotonic() - last_fresh > self.c['feedback_timeout']:
                raise TimeoutError('Feedback timeout')
            complete_axes = f and all(a < len(f.get('statuswords', [])) for a in self.axes)
            if serial > after and complete_axes and f.get('process_data_valid') and predicate(f): return f
            self.cancel.wait(0.01) if not cleanup else time.sleep(0.01)
        raise TimeoutError('Condition timeout: ' + self.step)

    def run(self):
        if not self.run_lock.acquire(False): raise RuntimeError('Run already active')
        if self.state != 'idle':
            self.run_lock.release()
            raise RuntimeError('One run only; no resume')
        outcome = 'completed'
        try:
            self.checkpoint()
            self.state = 'running'
            self.feedback.monitor = True
            self.step = 'common profile'
            for i, a in enumerate(self.axes):
                self.checkpoint()
                self.report(f'{self.step}: axis {a}')
                success(self.client.request({'cmd': 'system/axis/profile', 'axis': a,
                    'profile_acceleration': self.c['acceleration'][i],
                    'profile_deceleration': self.c['deceleration'][i]}, timeout=self.c['request_timeout']))
            for name, output_key, condition_key in (
                ('pick', 'grasp_outputs', 'grasp_conditions'), ('place', 'release_outputs', 'release_conditions')
            ):
                self.step = 'move ' + name
                self.report(self.step)
                self.checkpoint()
                success(self.client.request({'cmd': 'system/axes/move_abs', 'axes': self.axes,
                    'positions': self.c[name]['positions'], 'profile_velocities': self.c[name]['profile_velocities']},
                    timeout=self.c['request_timeout']))
                after = self.feedback.barrier(self.c['feedback_timeout'])
                self.evidence[name] = self.wait(lambda f: axes_complete(f, self.axes,
                    self.c[name]['positions'], self.c['position_tolerance']), after, self.c['move_timeout'])
                self.report(name + ': all axes position/target/reached/standstill confirmed')
                for output in self.c[output_key]:
                    self.step = output_key + ':' + output['kind']
                    self.checkpoint()
                    self.report(self.step)
                    success(self.client.request({'cmd': 'system/io/output_write', **output}, timeout=self.c['request_timeout']))
                if self.c[condition_key]:
                    self.step = condition_key
                    self.report(self.step)
                    after = self.feedback.barrier(self.c['feedback_timeout'])
                    self.evidence[condition_key] = self.wait(lambda f: inputs_match(f, self.c[condition_key]),
                        after, self.c['input_timeout'])
            self.checkpoint()
        except Cancelled as exc:
            outcome = 'cancelled'
            self.report(f'{self.step}: {exc}')
        except Exception as exc:
            outcome = 'failed'
            self.report(f'{self.step}: {type(exc).__name__}: {exc}')
        finally:
            self.state = 'stopping'
            self.step = 'cleanup Stop'
            try:
                self.checkpoint(cleanup=True)
                # Confirm ownership by read-only API even when Feedback has stalled.
                authority = success(self.client.request({'cmd': 'system/authority/status'}, timeout=self.c['request_timeout']))
                if not authority['owned_by_this_client']: raise RuntimeError('Authority lost; Stop not sent')
                self.checkpoint(cleanup=True)
                success(self.client.request({'cmd': 'system/axes/stop', 'axes': self.axes}, timeout=self.c['request_timeout']))
                after = self.feedback.barrier(self.c['feedback_timeout'])
                self.evidence['stopped'] = self.wait(lambda f: axes_complete(f, self.axes), after,
                    self.c['move_timeout'], cleanup=True)
                self.stop_confirmed = True
                self.report('Stop confirmed; I/O outputs retained')
            except Exception as exc:
                outcome = 'failed'
                self.report(f'INCOMPLETE: Stop NOT confirmed: {type(exc).__name__}: {exc}')
            if self.cancel.is_set() and outcome == 'completed': outcome = 'cancelled'
            if self.feedback.snapshot()[4] and outcome == 'completed': outcome = 'failed'
            self.state = outcome
            self.report(outcome)
            self.run_lock.release()
        return outcome
