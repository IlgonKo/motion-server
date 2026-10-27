"""Single-run sequence using the official transport directly. No API wrappers."""
import copy
import json
import math
import queue
import threading
import time


class Cancelled(Exception):
    pass


def success(response):
    if response.get('result') != 'success':
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response['data']


def validate(c):
    if (c['host'], c['port']) != ('127.0.0.1', 54786):
        raise ValueError('Only the authorized Mock endpoint is permitted')
    axes = list(c['axes'].values())
    if list(c['axes']) != ['X', 'Y', 'Z'] or len(set(axes)) != 3 or any(type(a) is not int or a < 0 for a in axes):
        raise ValueError('Invalid X/Y/Z mapping')
    for key in ('acceleration', 'deceleration', 'position_tolerance', 'velocity_tolerance',
                'request_timeout', 'move_timeout', 'input_timeout', 'feedback_timeout'):
        if type(c[key]) not in (float, int) or not math.isfinite(c[key]) or c[key] <= 0:
            raise ValueError(key)
    for point in ('pick', 'place'):
        for key in ('positions', 'profile_velocities'):
            values = c[point][key]
            if len(values) != 3 or any(type(v) not in (float, int) or not math.isfinite(v) or
                                     (key == 'profile_velocities' and v <= 0) for v in values):
                raise ValueError(point + '/' + key)
    for item in c['outputs'] + c['grip_inputs'] + c['release_inputs']:
        if not isinstance(item['io'], str) or not item['io'] or item['kind'] not in ('digital', 'analog'):
            raise ValueError('Invalid I/O')
        if any(type(item[k]) is not int or item[k] < 0 for k in ('slot', 'channel')):
            raise ValueError('Invalid slot/channel')
        keys = ('grip', 'release') if 'grip' in item else ('value',)
        if any(type(item[k]) is not (bool if item['kind'] == 'digital' else int) for k in keys):
            raise ValueError('Boolean digital / integer analog required')
        if 'op' in item and (item['op'] not in ('eq', 'ge') or (item['kind'] == 'digital' and item['op'] != 'eq')):
            raise ValueError('Invalid input comparison')


def input_value(f, item, direction='inputs'):
    device = next((d for d in f['io']['devices'] if d['id'] == item['io']), None)
    if device is None:
        raise KeyError(item['io'])
    module = next((m for m in device['modules'] if m['slot'] == item['slot']), None)
    if module is None:
        raise KeyError(item['slot'])
    return module[direction][item['kind']][item['channel']]


def inputs_met(f, conditions):
    try:
        return all((input_value(f, i) == i['value'] if i['op'] == 'eq'
                    else input_value(f, i) >= i['value']) for i in conditions)
    except (KeyError, IndexError, StopIteration, TypeError):
        return False


def motion_met(f, axes, targets=None, tolerance=0.5):
    try:
        return all(not f['statuswords'][a] & 256 and
                   (targets is None or (f['statuswords'][a] & 1024 and
                    abs(f['actual_positions'][a] - targets[n]) <= tolerance and
                    abs(f['target_positions'][a] - targets[n]) <= 1e-7))
                   for n, a in enumerate(axes))
    except (KeyError, IndexError, TypeError):
        return False


class Feedback:
    """Only queue consumer; barrier discards accumulated data after Success.

    Serial/time are local observations, never server operation identifiers.
    Loss/fault are latched even if a later snapshot becomes healthy.
    """
    def __init__(self, client, c):
        self.client, self.c = client, c
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.barrier = threading.Event()
        self.ack = threading.Event()
        self.serial, self.received, self.latest = 0, time.monotonic(), None
        self.owned = self.armed = False
        self.loss = self.fault = ''
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self):
        while not self.done.is_set():
            with self.lock:
                if not self.client.is_connected:
                    self.loss = 'Connection lost; no resume permitted'
                    self.latest = None
            try:
                # While marking, drain without a blocking interval: feedback may
                # arrive every 10 ms, so a timed empty read can starve forever.
                f = self.client.get_feedback(timeout=0 if self.barrier.is_set() else 0.01)
                with self.lock:
                    owns = f.get('command_authority', {}).get('owned_by_this_client') is True
                    if self.owned and not owns:
                        self.loss = 'Command authority lost'
                    self.owned = owns
                    if self.armed and f.get('process_data_valid') is True:
                        words = f.get('statuswords', [])
                        if any(a < len(words) and words[a] & 8 for a in self.c['axes'].values()) or f.get('server_health', {}).get('fault_count', 0):
                            self.fault = 'Runtime Fault'
                    self.latest, self.received = f, time.monotonic()
                    self.serial += 1
                # A barrier is acknowledged only when this consumer reaches queue.Empty.
                continue
            except queue.Empty:
                if self.barrier.is_set():
                    self.barrier.clear()
                    self.ack.set()
            except Exception as exc:
                with self.lock:
                    self.loss = 'Feedback consumer failed: ' + repr(exc)
                return

    def mark(self):
        self.ack.clear()
        self.barrier.set()
        if not self.ack.wait(self.c['feedback_timeout']):
            raise TimeoutError('Feedback barrier timeout')
        with self.lock:
            return self.serial

    def check(self, cancel, cleanup=False):
        with self.lock:
            if not self.client.is_connected or self.loss:
                raise RuntimeError(self.loss or 'Connection lost')
            if not cleanup:
                if cancel.is_set():
                    raise Cancelled('Stop/Ctrl+C')
                if self.fault:
                    raise RuntimeError(self.fault)
                if time.monotonic() - self.received > self.c['feedback_timeout']:
                    raise TimeoutError('Feedback timeout')

    def wait(self, predicate, after, timeout, cancel, cleanup=False):
        deadline = time.monotonic() + timeout
        while True:
            self.check(cancel, cleanup)
            with self.lock:
                serial, received, f = self.serial, self.received, self.latest
                fresh = time.monotonic() - received <= self.c['feedback_timeout']
                complete_axes = f and all(len(f.get(k, [])) > max(self.c['axes'].values())
                                          for k in ('actual_positions', 'target_positions', 'statuswords'))
                if serial > after and fresh and complete_axes and f.get('process_data_valid') is True and self.owned:
                    if predicate(f):
                        return copy.deepcopy(f)
            if not fresh:
                raise TimeoutError('Feedback timeout')
            if time.monotonic() >= deadline:
                raise TimeoutError('Condition timeout')
            time.sleep(0.01)


def run(client, config, cancel=None, log=print):
    c = copy.deepcopy(config)
    validate(c)
    cancel = cancel or threading.Event()
    axes = list(c['axes'].values())
    report = {'state': 'idle', 'stage': 'connect', 'cleanup_complete': False, 'events': []}
    fb = None
    owned = False
    authority_attempted = False
    attempted = False
    def event(stage, data=None):
        report['stage'] = stage
        item = {'stage': stage, 'monotonic': time.monotonic(), 'data': data}
        report['events'].append(item)
        log(json.dumps(item, ensure_ascii=False))
    try:
        client.start()
        deadline = time.monotonic() + c['request_timeout']
        while not client.wait_connected(timeout=0.05):
            if cancel.is_set():
                raise Cancelled('Stop/Ctrl+C')
            if time.monotonic() >= deadline:
                raise TimeoutError('Connection timeout: ' + str(getattr(client, 'last_error', '')))
        fb = Feedback(client, c)
        fb.thread.start()
        for role, axis in c['axes'].items():
            fb.check(cancel)
            event('metadata/' + role)
            data = success(client.request({'cmd': 'system/axis/status', 'axis': axis}, timeout=c['request_timeout']))
            event('metadata/' + role, data['axis_metadata'])
            if any(data['axis_metadata'].get(k) != v for k, v in c['units'].items()):
                raise ValueError('Axis metadata unit mismatch; review settings')
        fb.check(cancel)
        event('authority/request')
        authority_attempted = True
        data = success(client.request({'cmd': 'system/authority/request'}, timeout=c['request_timeout']))
        owned = data['owned_by_this_client']
        if not owned or not data['granted']:
            raise RuntimeError('Authority denied: ' + json.dumps(data))
        fb.wait(lambda f: True, fb.mark(), c['feedback_timeout'], cancel)
        report['state'] = 'running'
        # Fault monitoring begins with Run; no Homing/Enable/limit preflight.
        fb.armed = True
        for axis in axes:
            fb.check(cancel)
            event('profile/' + str(axis))
            attempted = True
            success(client.request({'cmd': 'system/axis/profile', 'axis': axis,
                                   'profile_acceleration': c['acceleration'],
                                   'profile_deceleration': c['deceleration']}, timeout=c['request_timeout']))
        for point, output, conditions in (('pick', 'grip', c['grip_inputs']),
                                           ('place', 'release', c['release_inputs'])):
            fb.check(cancel)
            event(point + '/move')
            success(client.request({'cmd': 'system/axes/move_abs', 'axes': axes,
                                   'positions': c[point]['positions'],
                                   'profile_velocities': c[point]['profile_velocities']}, timeout=c['request_timeout']))
            event(point + '/accepted')
            snapshot = fb.wait(lambda f: motion_met(f, axes, c[point]['positions'], c['position_tolerance']),
                               fb.mark(), c['move_timeout'], cancel)
            event(point + '/conditions_met', snapshot)
            for item in c['outputs']:
                fb.check(cancel)
                event(output + '/output', item)
                success(client.request({'cmd': 'system/io/output_write',
                                       **{k: item[k] for k in ('io', 'slot', 'kind', 'channel')},
                                       'value': item[output]}, timeout=c['request_timeout']))
                event(output + '/accepted')
            if conditions:
                snapshot = fb.wait(lambda f: inputs_met(f, conditions), fb.mark(), c['input_timeout'], cancel)
                event(output + '/inputs_met', snapshot)
        fb.check(cancel)
        report['state'] = 'stopping'
    except (Exception, KeyboardInterrupt) as exc:
        report['state'] = 'cancelled' if isinstance(exc, (Cancelled, KeyboardInterrupt)) else 'failed'
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['failed_stage'] = report['stage']
        event('stopping', report['error'])
    finally:
        if authority_attempted and not owned and fb:
            try:
                fb.check(cancel, cleanup=True)
                owned = success(client.request({'cmd': 'system/authority/status'}, timeout=c['request_timeout']))['owned_by_this_client']
            except Exception as exc:
                report['cleanup_error'] = f'INCOMPLETE: authority/Stop unconfirmed: {exc}'
        if owned and fb:
            try:
                fb.check(cancel, cleanup=True)
                # Read current connection-owned authority before cleanup. Never reacquire.
                data = success(client.request({'cmd': 'system/authority/status'}, timeout=c['request_timeout']))
                if not data['owned_by_this_client']:
                    raise RuntimeError('No authority: Stop not sent')
                fb.check(cancel, cleanup=True)
                event('cleanup/stop')
                success(client.request({'cmd': 'system/axes/stop', 'axes': axes}, timeout=c['request_timeout']))
                snapshot = fb.wait(lambda f: motion_met(f, axes), fb.mark(), c['move_timeout'], cancel, cleanup=True)
                report['cleanup_complete'] = True
                event('cleanup/standstill', snapshot)
            except (Exception, KeyboardInterrupt) as exc:
                report['cleanup_error'] = f'INCOMPLETE: Stop/Standstill unconfirmed: {exc}'
            try:
                fb.check(cancel, cleanup=True)
                data = success(client.request({'cmd': 'system/authority/status'}, timeout=c['request_timeout']))
                if data['owned_by_this_client']:
                    event('authority/release')
                    data = success(client.request({'cmd': 'system/authority/release'}, timeout=c['request_timeout']))
                    if data['owned_by_this_client']:
                        raise RuntimeError('Authority release not confirmed')
                    report['authority_released'] = True
            except (Exception, KeyboardInterrupt) as exc:
                report['release_error'] = f'INCOMPLETE: {exc}'
        elif attempted:
            report['cleanup_error'] = 'INCOMPLETE: Stop not sent'
        if fb:
            fb.done.set()
            fb.thread.join(timeout=1)
        client.stop()
    if report['state'] == 'stopping':
        if cancel.is_set():
            report['state'] = 'cancelled'
            report['error'] = 'Stop/Ctrl+C during cleanup'
        elif fb and fb.fault:
            report['state'] = 'failed'
            report['error'] = fb.fault
        else:
            report['state'] = 'completed' if report['cleanup_complete'] and report.get('authority_released') else 'failed'
    return report
