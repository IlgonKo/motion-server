"""Test-only widget doubles. Does NOT prove real Tcl/Tk rendering or OS focus behavior."""
import heapq
import threading
import time
import tkinter as tk
from tkinter import ttk

UI_THREAD=threading.get_ident()

def ui_only():
    assert threading.get_ident()==UI_THREAD,'Tk call from worker thread'

class Variable:
    def __init__(self,value=None,**kwargs): ui_only(); self.value=value
    def get(self): ui_only(); return self.value
    def set(self,value): ui_only(); self.value=value

class Widget:
    def __init__(self,*args,**kwargs): ui_only(); self.options=kwargs
    def pack(self,**kwargs): ui_only()
    def configure(self,**kwargs): ui_only(); self.options.update(kwargs)
    def insert(self,*args): ui_only()
    def see(self,*args): ui_only()
    def invoke(self):
        ui_only()
        if self.options.get('state')!='disabled': return self.options['command']()

class Root:
    def __init__(self):
        ui_only(); self.queue=[]; self.index=0; self.alive=True; self.protocols={}; self.bindings={}; self.tk=self
    def title(self,*args): ui_only()
    def after(self,ms,callback):
        ui_only(); self.index+=1; heapq.heappush(self.queue,(time.monotonic()+ms/1000,self.index,callback))
    def bind(self,event,callback): ui_only(); self.bindings[event]=callback
    def event_generate(self,event): ui_only(); self.bindings[event](None)
    def protocol(self,name,callback=None):
        ui_only()
        if callback is not None: self.protocols[name]=callback
        return self.protocols[name]
    def call(self,command,callback): ui_only(); assert command=='eval'; callback()
    def destroy(self): ui_only(); self.alive=False
    def mainloop(self):
        ui_only(); deadline=time.monotonic()+50
        while self.alive:
            assert time.monotonic()<deadline,'Test-only event loop deadline'
            if self.queue and self.queue[0][0]<=time.monotonic(): heapq.heappop(self.queue)[2]()
            else: time.sleep(.002)

def install():
    tk.Tk=Root; tk.StringVar=Variable; tk.Text=Widget
    ttk.Frame=ttk.Label=ttk.Entry=ttk.Button=Widget
