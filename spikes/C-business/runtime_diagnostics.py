"""Bounded timing diagnostics. Does not change observation clocks or TTL."""
from datetime import datetime
from contextlib import contextmanager
from contextvars import ContextVar
import time
import json
import logging

_active=ContextVar('runtime_phase_diagnostics',default=None)

@contextmanager
def phase(name):
    diagnostics=_active.get()
    if diagnostics is None:
        yield;return
    started=time.monotonic();cpu=time.thread_time()
    prior=diagnostics.value.get('active_phase')
    diagnostics.value['active_phase']={'name':name,'started_at':datetime.now().astimezone().isoformat()}
    try:yield
    finally:
        record={'wall_seconds':time.monotonic()-started,'thread_cpu_seconds':time.thread_time()-cpu}
        previous=diagnostics.value['phases'].get(name,{})
        record['max_wall_seconds']=max(previous.get('max_wall_seconds',0),record['wall_seconds'])
        record['max_wall_thread_cpu_seconds']=(record['thread_cpu_seconds'] if record['wall_seconds']>=previous.get('max_wall_seconds',0)
                                               else previous.get('max_wall_thread_cpu_seconds'))
        if record['wall_seconds']>=1:
            logging.getLogger('aquaguard.runtime.phase').warning('runtime_phase %s',json.dumps({'name':name,**record}))
        diagnostics.value['phases']={**diagnostics.value['phases'],name:record}
        diagnostics.value['active_phase']=prior


class RuntimeDiagnostics:
    def __init__(self):
        self.value={'cycles':0,'failures':0,'max_gap_seconds':0,'max_advance_seconds':0,
                    'last_success_at':None,'last_cycle':None,'phases':{},'active_phase':None}
        self.previous=None

    @contextmanager
    def scope(self):
        token=_active.set(self)
        try:yield
        finally:_active.reset(token)

    def begin(self,utc,monotonic,cpu):
        gap=None if self.previous is None else monotonic-self.previous['end']
        wall_gap=None if self.previous is None else (datetime.fromisoformat(utc.replace('Z','+00:00'))-datetime.fromisoformat(self.previous['utc'].replace('Z','+00:00'))).total_seconds()
        return dict(start=monotonic,cpu=cpu,started_at=utc,gap_seconds=gap,wall_start_gap_seconds=wall_gap)

    def finish(self,cycle,*,end,cpu,ended_at,step_seconds,tick_seconds,error_type=None):
        duration=end-cycle['start']
        record={key:value for key,value in cycle.items() if key not in ('start','cpu')}
        record.update(ended_at=ended_at,advance_seconds=duration,cpu_seconds=cpu-cycle['cpu'],
                      step_seconds=step_seconds,tick_seconds=tick_seconds,error_type=error_type)
        self.value['cycles']+=1
        self.value['failures']+=int(error_type is not None)
        self.value['max_gap_seconds']=max(self.value['max_gap_seconds'],cycle['gap_seconds'] or 0)
        self.value['max_advance_seconds']=max(self.value['max_advance_seconds'],duration)
        self.value['last_cycle']=record
        if error_type is None:self.value['last_success_at']=ended_at
        self.previous={'end':end,'utc':cycle['started_at']}
        return record
