"""Tk/ttk view; all transport and bounded waits run in workers."""
from pathlib import Path
import sys
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from motion_server_reference_client import MotionServerClient
from .sequence import Feedback, Sequence, success
from .settings import CONFIG, load_config, check_metadata

class Panel:
    def __init__(self, root, config_path=CONFIG):
        self.root = root
        self.events = queue.Queue()
        self.history = []
        self.client = self.feedback = self.sequence = None
        self.busy = self.closing = self.shutdown_started = False
        self.closed = False
        self.metadata_ok = False
        self.config_error = ''
        try:
            self.config = load_config(config_path)
        except Exception as exc:
            self.config_error = f'Configuration error; Run blocked: {exc}'
            self.config = {'host':'127.0.0.1','port':52728,'feedback_timeout':2,'request_timeout':5}
        self.host = tk.StringVar(value=self.config['host'])
        self.port = tk.StringVar(value=str(self.config['port']))
        self.status = tk.StringVar(value='Disconnected')
        self.phase = tk.StringVar(value='idle')
        self.error = tk.StringVar(value=self.config_error)
        root.title('XYZ Pick & Place — one cycle / no Teaching')
        top = ttk.Frame(root, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text='Host').pack(side='left')
        ttk.Entry(top, textvariable=self.host, width=18).pack(side='left')
        ttk.Label(top, text='Port').pack(side='left')
        ttk.Entry(top, textvariable=self.port, width=8).pack(side='left')
        self.buttons = {}
        for label, action in [('Connect',self.connect),('Disconnect',self.disconnect),('Request authority',lambda:self.authority('request')),('Release authority',lambda:self.authority('release')),('Run',self.run),('Stop',self.stop)]:
            button = ttk.Button(top, text=label, command=action)
            button.pack(side='left')
            self.buttons[label] = button
        for variable in (self.status,self.phase,self.error):
            ttk.Label(root,textvariable=variable,wraplength=1000).pack(anchor='w',padx=8)
        self.log = tk.Text(root,width=130,height=20,state='disabled')
        self.log.pack(fill='both',expand=True,padx=8,pady=8)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<FocusOut>',self.focus_out)
        root.after(30,self.tick)

    def report(self, message):
        self.events.put(('log',str(message)))

    def submit(self, operation):
        if self.busy or self.closing:
            return
        self.busy = True
        def worker():
            try:
                operation()
            except Exception as exc:
                self.events.put(('error',str(exc)))
            finally:
                self.events.put(('done',None))
        threading.Thread(target=worker,daemon=False).start()

    def connect(self):
        if self.config_error:
            self.report(self.config_error)
            return
        try:
            host,port = self.host.get().strip(),int(self.port.get())
            if not host or not 1 <= port <= 65535:
                raise ValueError('Host/Port invalid')
        except ValueError as exc:
            self.report(exc)
            return
        def operation():
            if self.client:
                self.shutdown()
            self.metadata_ok = False
            self.client = MotionServerClient(host,port,request_timeout=self.config['request_timeout'],feedback_queue_size=1)
            self.feedback = Feedback(self.client)
            self.client.start()
            self.feedback.start()
            if not self.client.wait_connected(self.config['request_timeout']):
                raise RuntimeError(self.client.last_error)
            self.report('Metadata: '+str(check_metadata(success(self.client.request({'cmd':'system/axes/status'})),self.config)))
            self.metadata_ok = True
            self.report('Connected. Request authority explicitly.')
        self.submit(operation)

    def shutdown(self):
        try:
            if self.client:
                if self.client.is_connected:
                    data = success(self.client.request({'cmd':'system/authority/status'}))
                    if data.get('owned_by_this_client'):
                        success(self.client.request({'cmd':'system/authority/release'}))
                        self.report('Authority released')
                else:
                    self.report('Disconnected: explicit authority release unavailable')
        finally:
            if self.client:
                self.client.stop()
                self.feedback.close()
            self.client = self.feedback = None
            self.metadata_ok = False
            self.report('Connection closed')

    def disconnect(self):
        self.submit(self.shutdown)

    def authority(self, action):
        def operation():
            data = success(self.client.request({'cmd':f'system/authority/{action}'}))
            self.report(data)
            if action == 'request' and not data.get('owned_by_this_client'):
                raise RuntimeError('Authority denied')
        self.submit(operation)

    def run(self):
        if self.busy or self.closing or not self.metadata_ok or self.config_error:
            return
        try:
            self.sequence = Sequence(self.client,self.feedback,self.config,{},self.report)
        except Exception as exc:
            self.report(f'Run blocked: {exc}')
            return
        self.submit(self.sequence.run)

    def stop(self):
        if self.busy and self.sequence and self.sequence.state in ('idle','running','stopping'):
            self.sequence.cancel.set()
            self.phase.set('stopping: cancellation requested; pending request must finish')
            self.report('Stop requested')
        elif not self.busy and self.client:
            def operation():
                guard = Sequence(self.client,self.feedback,self.config,{},self.report)
                success(self.client.request({'cmd':'system/axes/stop','axes':guard.axes}))
                guard.wait(lambda f:all(not f['statuswords'][a]&256 for a in guard.axes),self.feedback.barrier(),self.config['stage_timeout'],cleanup=True)
                self.report('Idle Stop / Standstill confirmed')
            self.submit(operation)

    def focus_out(self, event):
        # No Teaching/Jog was selected. Focus changes do not cancel automatic Run.
        pass

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.busy and self.sequence:
            self.sequence.cancel.set()
        self.report('Close requested: await bounded cleanup, then release/disconnect')

    def tick(self):
        while True:
            try:
                kind,value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'done':
                self.busy = False
            else:
                line = f'{time.strftime("%H:%M:%S")} {value}'
                self.history.append(line)
                try:
                    with Path(__file__).with_name('gui.log').open('a',encoding='utf-8') as output:
                        output.write(line+'\n')
                except OSError as exc:
                    self.error.set(f'Log write failed: {exc}')
                    print(f'Log write failed: {exc}',file=sys.stderr)
                if kind == 'error' or 'NOT confirmed' in value:
                    print(line,file=sys.stderr)
                self.log.configure(state='normal')
                self.log.insert('end',line+'\n')
                self.log.see('end')
                self.log.configure(state='disabled')
                if kind == 'error':
                    self.error.set('FAILED / shutdown may be incomplete: '+value)
                    self.phase.set('failed')
        connected = bool(self.client and self.client.is_connected)
        serial,received,value,loss = self.feedback.snapshot() if self.feedback else (0,0,None,0)
        fresh = connected and time.monotonic()-received <= self.config['feedback_timeout']
        value = value or {}
        owned = fresh and value.get('command_authority',{}).get('owned_by_this_client',False)
        self.status.set(f'Connected: {connected} | Authority: {owned} | Feedback fresh: {fresh} | Valid: {value.get("process_data_valid")}\nServer: {value.get("server_health",{})}\nPositions: {value.get("actual_positions",[])}')
        if self.sequence:
            state = 'stopping' if self.busy and self.sequence.cancel.is_set() else self.sequence.state
            self.phase.set(f'{state}: {self.sequence.step} | Stop confirmed: {self.sequence.cleanup_confirmed}')
        enabled = {'Connect':not connected,'Disconnect':self.client is not None,'Request authority':connected and not owned,'Release authority':owned,'Run':owned and self.metadata_ok and not self.config_error}
        for label,allowed in enabled.items():
            self.buttons[label].configure(state='normal' if allowed and not self.busy and not self.closing else 'disabled')
        if self.closing and not self.busy:
            if not self.shutdown_started:
                self.shutdown_started = True
                self.closing = False
                self.submit(self.shutdown)
                self.closing = True
            else:
                self.closed = True
                self.root.destroy()
                return
        self.root.after(30,self.tick)

def show(config_path=CONFIG):
    root = tk.Tk()
    Panel(root,config_path)
    root.mainloop()

if __name__ == '__main__':
    show()
