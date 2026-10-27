"""Independent test instrumentation. Never supplied to generation agent."""
import json
import select
import socket
import threading
import time


class Observer:
    def __init__(self, port, delay_command=None, listen_port=0):
        self.port_target = port
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1',listen_port))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.port = self.listener.getsockname()[1]
        self.stop = threading.Event()
        self.disconnect = threading.Event()
        self.records = []
        self.last_feedback = None
        self.error = None
        self.delay_command = delay_command
        self.delayed = threading.Event()
        self.delivered = threading.Event()
        self.thread = threading.Thread(target=self.run,daemon=True)
        self.thread.start()

    def record(self, direction, data):
        self.records.append({'time':time.monotonic(),'direction':direction,'data':data})

    def run(self):
        client = server = None
        try:
            while not self.stop.is_set():
                try:
                    client,_ = self.listener.accept()
                    break
                except socket.timeout:
                    pass
            if client is None:
                return
            server = socket.create_connection(('127.0.0.1',self.port_target),timeout=3)
            client.settimeout(2)
            buffers = {client:b'',server:b''}
            commands = {}
            delayed = []
            while not self.stop.is_set() and not self.disconnect.is_set():
                for source in select.select([client,server],[],[],.01)[0]:
                    chunk=source.recv(65536)
                    if not chunk:
                        return
                    buffers[source]+=chunk
                    while b'\n' in buffers[source]:
                        line,buffers[source]=buffers[source].split(b'\n',1)
                        value=json.loads(line)
                        key=value.get('request_id')
                        if source is client:
                            self.record('request',value)
                            commands[key]=value.get('cmd')
                            server.sendall(line+b'\n')
                        else:
                            if value.get('type')=='system/feedback':
                                self.last_feedback=value
                            self.record('server',value)
                            if self.delay_command and key and commands.get(key)==self.delay_command:
                                self.delay_command=None
                                delayed.append((time.monotonic()+6,line+b'\n'))
                                self.delayed.set()
                            else:
                                client.sendall(line+b'\n')
                for due,line in delayed[:]:
                    if time.monotonic()>=due:
                        client.sendall(line)
                        delayed.remove((due,line))
                        self.delivered.set()
        except ConnectionError:
            pass
        except Exception as exc:
            self.error=repr(exc)
        finally:
            for s in (client,server):
                if s:
                    s.close()

    def close(self):
        self.stop.set()
        self.thread.join(4)
        self.listener.close()
        if self.thread.is_alive():
            raise RuntimeError('Observer did not stop')

    def requests(self):
        return [r['data'] for r in self.records if r['direction']=='request']
