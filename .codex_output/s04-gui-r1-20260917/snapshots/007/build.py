from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
p = (root/'reference_clients/python/examples/pick_place/program.py').read_text(encoding='utf-8')
p = p[:p.index('\ndef capture(')]
p = p[:p.index('\ndef save_points(')] + p[p.index('\ndef number('):]
a = p.index('        if c["teaching"]:')
b = p.index('        for role in roles:', a + 30)
# Remove complete optional Teaching block.
b = p.index('        for role in roles:\n            number(step', a)
p = p[:a] + p[b:]
p = p.replace('def prepare(config, points, *, manual=False):', 'def prepare(config, points=None, *, manual=False):')
p = p.replace('        self.loss = 0\n', '        self.loss = 0\n        self.fault_serial = 0\n        self.flush = threading.Event()\n        self.flushed = threading.Event()\n')
p = p.replace('            try:\n                value = self.client.get_feedback', '''            if self.flush.is_set():
                # Only this consumer drains the transport queue. Discard accumulated data.
                while not self.done.is_set():
                    try:
                        self.client.get_feedback(timeout=0)
                    except queue.Empty:
                        break
                self.flush.clear()
                self.flushed.set()
            try:
                value = self.client.get_feedback''')
p = p.replace('                self.serial += 1', '''                self.serial += 1
                if value.get("process_data_valid") and (value.get("server_health", {}).get("fault_count", 0)
                        or any(s & 8 for s in value.get("statuswords", []))):
                    self.fault_serial = self.serial''')
a = p.index('    def snapshot(self):')
p = p[:a] + '''    def barrier(self, timeout=2):
        self.flushed.clear()
        self.flush.set()
        if not self.flushed.wait(timeout):
            raise TimeoutError("Feedback consumer barrier timeout")
        return self.snapshot()[0]

''' + p[a:]
p = p.replace('        self.monitor_after = None', '        self.monitor_after = None\n        self.cleanup_confirmed = False')
p = p.replace('or any(\n                    value["statuswords"][a] & 8 for a in self.axes)', 'or self.feedback.fault_serial > self.monitor_after')
p = p.replace('and serial > self.monitor_after', 'and serial > self.monitor_after')
p = p.replace('            if serial > after and value.get("process_data_valid") and predicate(value):\n                return value', '''            if serial > after and value.get("process_data_valid"):
                try:
                    matched = predicate(value)
                except (KeyError, IndexError, TypeError):
                    matched = False
                if matched:
                    return value''')
p = p.replace('            self.state = "running"', '            self.state = "running"\n            self.monitor_after = self.feedback.snapshot()[0]', 1)
p = p.replace('self.feedback.snapshot()[0]', 'self.feedback.barrier(self.config["feedback_timeout"])')
# Initial fault epoch must not flush away early-run monitoring data.
p = p.replace('self.monitor_after = self.feedback.barrier(self.config["feedback_timeout"])', 'self.monitor_after = self.feedback.snapshot()[0]')
p = p.replace('                self.checkpoint(cleanup=True)\n                success(self.client.request({"cmd": "system/axes/stop"', '''                if not self.client.is_connected or self.feedback.snapshot()[3] != self.loss:
                    raise RuntimeError("Connection/authority loss: Stop cleanup unavailable")
                authority = success(self.client.request({"cmd": "system/authority/status"}, timeout=self.config["request_timeout"]))
                if not authority.get("owned_by_this_client"):
                    raise RuntimeError("No authority: Stop cleanup unavailable")
                success(self.client.request({"cmd": "system/axes/stop"''')
p = p.replace('cleanup=True)\n            except Exception', 'cleanup=True)\n                self.cleanup_confirmed = True\n                self.report("Stop / Standstill confirmed; I/O unchanged by cleanup")\n            except Exception')
p = p.replace('            self.step = "Cleanup"', '            self.step = "Cleanup"\n            self.report(self.step)')
p = p.replace('            if outcome != "completed":', '            if outcome != "completed":')
# No failure I/O policy choices in this requested deliverable.
a = p.index('            if outcome != "completed":')
b = p.index('            self.state = outcome', a)
p = p[:a]+p[b:]
p = p.replace('    roles = c["roles"]', '''    if c.get("teaching") or c.get("failure_outputs"):
        raise ValueError("Teaching unsupported; failure outputs must remain unchanged")
    roles = c["roles"]''')
(root/'generated/sequence.py').write_text(p, encoding='utf-8')
c = json.loads((root/'reference_clients/python/examples/pick_place/sequence.json').read_text())
c['port'] = 52728
c['pick'] = {'positions': dict(zip('XYZ', [50,60,70])), 'velocities': dict(zip('XYZ',[50,50,40]))}
c['place'] = {'positions': dict(zip('XYZ',[100,110,120])), 'velocities': dict(zip('XYZ',[50,50,20]))}
c.pop('teaching_motion')
(root/'generated/sequence.json').write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8')
