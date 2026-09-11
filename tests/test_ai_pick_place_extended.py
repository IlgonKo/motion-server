"""S04 real Mock TCP GUI and test-launcher WKC fault checks. No hardware."""
import json
import threading
import time
import tkinter as tk
import unittest

from tests import test_ai_pick_place_tcp as tcp
from tests.test_ai_pick_place_tcp import Sequence, success, load_json
from examples.pick_place.gui import Panel
from tests.sequence_tcp_proxy import ResponseDelayProxy


class ExtendedTests(unittest.TestCase):
    setUp = tcp.PickPlaceTcpTests.setUp
    tearDown = tcp.PickPlaceTcpTests.tearDown
    cleanup = tcp.PickPlaceTcpTests.cleanup
    wait_for = tcp.PickPlaceTcpTests.wait_for
    set_inputs = tcp.PickPlaceTcpTests.set_inputs
    inject_wkc = True

    def panel(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(lambda: self.destroy(root))
        self.config['teaching'] = True
        path = self.folder / 'sequence.json'
        points_path = self.folder / 'points.json'
        path.write_text(json.dumps(self.config), encoding='utf-8')
        points = {name: {r: {'position': value, 'unit': 'mm'}
                        for r, value in self.config[stage]['positions'].items()}
                  for name, stage in [('Pick', 'pick'), ('Place', 'place')]}
        points_path.write_text(json.dumps(points), encoding='utf-8')
        panel = Panel(root, path, points_path)
        panel.client, panel.feedback = self.client, self.feedback
        root.update()
        return root, panel

    @staticmethod
    def destroy(root):
        try:
            for pending in root.tk.call('after', 'info'):
                root.after_cancel(pending)
            root.destroy()
        except tk.TclError:
            pass

    def pump(self, root, condition, timeout=7):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail('GUI condition timeout')

    def test_teaching_capture_apply_save_reload_and_run_snapshot(self):
        self.set_inputs()
        root, panel = self.panel()
        original = panel.points_path.read_text()
        panel.point_name.set('Captured')
        panel.capture_point()
        captured = json.loads(panel.editor.get('1.0', 'end'))
        self.assertEqual(captured['X']['unit'], 'mm')
        self.assertAlmostEqual(captured['X']['position'], 0, places=2)
        panel.apply_point()
        self.assertEqual(panel.points_path.read_text(), original)
        panel.save()
        self.assertEqual(load_json(panel.points_path), panel.points)
        panel.run()
        panel.points['Place']['X']['position'] = 999
        panel.run()  # duplicate click must not start another worker
        self.pump(root, lambda: not panel.busy)
        self.assertEqual(panel.sequence.state, 'completed', panel.log.get('1.0', 'end'))
        moves = [m for m in self.messages if m['cmd'] == 'system/axes/move_abs']
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[1]['positions'][0], 1.)
        self.assertTrue(self.feedback.snapshot()[2]['command_authority']['owned_by_this_client'])

    def test_gui_jog_focus_loss_and_release(self):
        root, panel = self.panel()
        for release in (lambda: panel.focus_out(None), panel.jog_release.set):
            panel.jog('positive')
            self.pump(root, lambda: any(m['cmd'] == 'system/axis/jog_start' for m in self.messages))
            release()
            self.pump(root, lambda: not panel.busy)
            self.assertTrue(any(m['cmd'] == 'system/axis/jog_stop' for m in self.messages))
            self.assertFalse(self.feedback.snapshot()[2]['statuswords'][0] & 256)
            self.messages.clear()

    def test_gui_close_during_wait_stops_then_releases(self):
        root, panel = self.panel()
        panel.config['input_timeout'] = 10
        panel.run()
        self.pump(root, lambda: panel.sequence.step == 'grasp_conditions')
        ticks = []
        root.after(10, lambda: ticks.append(True))
        self.pump(root, lambda: bool(ticks))
        panel.close()
        self.pump(root, lambda: panel.client is None)
        def destroyed():
            try:
                return not root.winfo_exists()
            except tk.TclError:
                return True
        self.pump(root, destroyed)
        self.assertEqual(panel.sequence.state, 'cancelled')
        commands = [m['cmd'] for m in self.messages]
        self.assertLess(commands.index('system/axes/stop'), commands.index('system/authority/release'))
        self.assertEqual(commands.count('system/axes/move_abs'), 1)
        self.assertFalse(any('disable' in c for c in commands))

    def test_teaching_move_point_then_sequence_reapplies_profile(self):
        self.set_inputs()
        root, panel = self.panel()
        panel.point_name.set('Pick')
        panel.move_point()
        self.pump(root, lambda: not panel.busy)
        self.assertEqual(panel.sequence.state, 'completed', panel.log.get('1.0', 'end'))
        profiles = [m for m in self.messages if m['cmd'] == 'system/axis/profile']
        self.assertEqual(profiles[0]['profile_acceleration'], 20)
        self.messages.clear()
        panel.run()
        self.pump(root, lambda: not panel.busy)
        self.assertEqual(panel.sequence.state, 'completed', panel.log.get('1.0', 'end'))
        profiles = [m for m in self.messages if m['cmd'] == 'system/axis/profile']
        self.assertEqual(len(profiles), 3)
        self.assertEqual(profiles[0]['profile_acceleration'], 100)

    def test_actual_server_wkc_fault_aborts_sequence(self):
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        seq.config['input_timeout'] = 10
        worker = threading.Thread(target=seq.run)
        worker.start()
        try:
            end = time.monotonic() + 5
            while seq.step != 'grasp_conditions' and time.monotonic() < end:
                time.sleep(.01)
            self.assertEqual(seq.step, 'grasp_conditions')
            (self.folder / 'inject-wkc').touch()
            self.wait_for(lambda f: f['server_health']['fault_count'] > 0)
            worker.join(7)
            self.assertFalse(worker.is_alive())
            self.assertEqual(seq.state, 'failed', self.logs)
            self.assertTrue(any('Fault detected' in line for line in self.logs), self.logs)
            self.assertEqual(sum(m['cmd'] == 'system/axes/move_abs' for m in self.messages), 1)
            self.assertIsNone(self.process.poll())
            success(self.client.request({'cmd': 'system/server/status'}))
        finally:
            seq.cancel.set()
            worker.join(7)


class DelayedResponseTests(unittest.TestCase):
    setUp = tcp.PickPlaceTcpTests.setUp
    tearDown = tcp.PickPlaceTcpTests.tearDown
    cleanup = tcp.PickPlaceTcpTests.cleanup
    wait_for = tcp.PickPlaceTcpTests.wait_for
    set_inputs = tcp.PickPlaceTcpTests.set_inputs
    panel = ExtendedTests.panel
    destroy = staticmethod(ExtendedTests.destroy)
    pump = ExtendedTests.pump

    def start_proxy(self, port):
        self.proxy = ResponseDelayProxy(port)
        self.addCleanup(self.proxy.close)
        return self.proxy.port

    def test_move_response_timeout_no_replay_or_late_resume(self):
        self.set_inputs()
        self.config['request_timeout'] = .5
        self.proxy.delay = 1.5
        self.proxy.command = 'system/axes/move_abs'
        seq = Sequence(self.client, self.feedback, self.config, {}, self.logs.append)
        self.assertEqual(seq.run(), 'failed', self.logs)
        self.assertTrue(self.proxy.delayed.is_set())
        self.assertTrue(self.proxy.delivered.wait(3))
        self.assertEqual(seq.state, 'failed')
        self.assertEqual(sum(m['cmd'] == 'system/axes/move_abs' for m in self.messages), 1)
        self.assertTrue(any(m['cmd'] == 'system/axes/stop' for m in self.messages))
        self.assertFalse(any(m['cmd'] == 'system/io/output_write' for m in self.messages))
        self.assertTrue(self.client.is_connected)
        self.wait_for(lambda f: all(not s & 256 for s in f['statuswords']))

    def test_gui_stop_responsive_while_move_response_is_delayed(self):
        self.set_inputs()
        self.config['request_timeout'] = .5
        self.proxy.delay = 1.5
        root, panel = self.panel()
        self.proxy.command = 'system/axes/move_abs'
        panel.run()
        self.pump(root, self.proxy.delayed.is_set)
        beats = []
        root.after(10, lambda: beats.append(True))
        panel.stop()
        self.pump(root, lambda: bool(beats), timeout=1)
        self.assertTrue(panel.busy)  # request is still pending, UI is not blocked
        self.pump(root, lambda: not panel.busy)
        self.assertEqual(panel.sequence.state, 'failed', panel.log.get('1.0', 'end'))
        self.assertTrue(self.proxy.delivered.wait(3))
        self.assertEqual(sum(m['cmd'] == 'system/axes/move_abs' for m in self.messages), 1)
        self.assertFalse(any(m['cmd'] == 'system/io/output_write' for m in self.messages))
