from pathlib import Path
p=Path('generated/sequence.py')
s=p.read_text(encoding='utf-8')
s=s.replace('        self.fault_serial = 0','        self.fault_serial = 0\n        self.owned = False')
s=s.replace('        owned = False\n','')
s=s.replace('                        self.client.get_feedback(timeout=0)','                        queued = self.client.get_feedback(timeout=0)\n                        if self.client.is_connected:\n                            self._publish(queued)')
a=s.index('            now_owned = value.get(')
b=s.index('    def barrier(',a)
s=s[:a]+'''            self._publish(value)

    def _publish(self, value):
        now_owned = value.get("command_authority", {}).get("owned_by_this_client", False)
        with self.lock:
            if self.owned and not now_owned:
                self.loss += 1
            self.owned = now_owned
            self.latest = value
            self.received = time.monotonic()
            self.serial += 1
            if value.get("process_data_valid") and (value.get("server_health", {}).get("fault_count", 0)
                    or any(s & 8 for s in value.get("statuswords", []))):
                self.fault_serial = self.serial

'''+s[b:]
s=s.replace('        for output in c[key]:\n', '''        for output in c[key]:
            if not isinstance(output["io"], str) or not output["io"].strip():
                raise ValueError("Output io ID required")
            if set(output) != {"io", "slot", "channel", "kind", "value"}:
                raise ValueError("Output fields must be io/slot/channel/kind/value")
''')
s=s.replace('        for condition in c[key]:\n', '''        for condition in c[key]:
            if not isinstance(condition["io"], str) or not condition["io"].strip():
                raise ValueError("Input io ID required")
''')
p.write_text(s,encoding='utf-8')
p=Path('generated/gui.py'); s=p.read_text(encoding='utf-8')
s=s.replace('import queue','from pathlib import Path\nimport sys\nimport queue',1)
s=s.replace("                self.history.append(line)",'''                self.history.append(line)
                try:
                    with Path(__file__).with_name('gui.log').open('a',encoding='utf-8') as output:
                        output.write(line+'\\n')
                except OSError as exc:
                    self.error.set(f'Log write failed: {exc}')
                    print(f'Log write failed: {exc}',file=sys.stderr)
                if kind == 'error' or 'NOT confirmed' in value:
                    print(line,file=sys.stderr)''')
p.write_text(s,encoding='utf-8')
