from pathlib import Path
p=Path('generated/sequence.py');s=p.read_text(encoding='utf-8')
s=s.replace('    def barrier(self, timeout=2):\n', '    def barrier(self, timeout=2, cancel=None):\n')
s=s.replace('        if not self.flushed.wait(timeout):\n            raise TimeoutError("Feedback consumer barrier timeout")', '''        deadline = time.monotonic() + timeout
        while not self.flushed.wait(.02):
            if cancel is not None and cancel.is_set():
                raise Cancelled("User Stop while waiting for new Feedback")
            if time.monotonic() >= deadline:
                raise TimeoutError("Feedback consumer barrier timeout")''')
s=s.replace('after = self.feedback.barrier(self.config["feedback_timeout"])', 'after = self.feedback.barrier(self.config["feedback_timeout"], self.cancel)')
s=s.replace('self.feedback.barrier(self.config["feedback_timeout"]), c["input_timeout"]', 'self.feedback.barrier(self.config["feedback_timeout"], self.cancel), c["input_timeout"]')
p.write_text(s,encoding='utf-8')
