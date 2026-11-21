"""Windows-owned loopback simulation backend. Imported without launching processes."""
import ast
from contextlib import closing
import ctypes
from ctypes import wintypes
import hashlib
import importlib.metadata
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]


def create_job():
    """Hold a kill-on-close job for self/descendants until process exit."""
    if os.name!='nt':raise OSError('Windows owned-process job required')
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',wintypes.DWORD),
                  ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',wintypes.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
    class Limits(ctypes.Structure):
        _fields_=[('basic',Basic),('io',ctypes.c_ulonglong*6),('process_memory',ctypes.c_size_t),
                  ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    kernel.GetCurrentProcess.restype=wintypes.HANDLE;kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise OSError('cannot create owned-process job')
    limits=Limits();limits.basic.flags=0x2000
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle);raise OSError('cannot bind owned-process job')
    return handle


def database_exit_checks(business,journal):
    """Never initializes either database; query failures remain failures."""
    checks={}
    for name,path in (('business',business),('journal',journal)):
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            db.execute('BEGIN')
            checks[name+'_quick_check']=[row[0] for row in db.execute('PRAGMA quick_check')]
            if name=='business':
                checks['duplicate_open_groups']=db.execute("SELECT count(*) FROM (SELECT device_id,event_type FROM events WHERE lifecycle='OPEN' GROUP BY device_id,event_type HAVING count(*)>1)").fetchone()[0]
            db.rollback()
    from mqtt_capacity_snapshot import snapshot
    checks['capacity']=snapshot(journal,business)
    checks['ok']=checks['business_quick_check']==['ok'] and checks['journal_quick_check']==['ok'] and checks['duplicate_open_groups']==0
    return checks


class LocalBackend:
    def __init__(self,broker,mqtt_port,http_port):
        self.broker=Path(broker).resolve();self.mqtt_port=mqtt_port;self.http_port=http_port
        self.active={};self.history=[];self.logs=[];self.seq=0;self.last_rows=[];self.job=None
        self.publisher_stop_file=None;self.runtime_versions=None
        self.token=uuid4().hex;self.runtime_versions=None;self.publisher_stop_file=None
        # Ignore system proxy configuration for both loopback APIs.
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def verify_revision(self,plan):
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT).returncode
        if revision!=plan['revision'] or dirty:raise ValueError('clean tracked source at planned revision required')

    def preflight(self,plan):
        if os.name!='nt':raise ValueError('this backend requires Windows Job Objects')
        if not self.broker.is_file():raise ValueError('existing local broker executable required')
        if any(type(port) is not int or not 1<=port<=65535 for port in (self.mqtt_port,self.http_port)) or self.mqtt_port==self.http_port:
            raise ValueError('distinct valid loopback ports required')
        self.verify_revision(plan)
        from mqtt_closeout_evidence import runtime_lock
        expected=plan.get('runtime_lock')
        if not isinstance(expected,dict):raise ValueError('offline prepared runtime lock required')
        self.runtime_versions=runtime_lock(ROOT,self.broker,expected.get('broker_version'))
        if self.runtime_versions!=expected:raise ValueError('runtime or broker differs from prepared lock')
        tree=ast.parse((ROOT/'spikes/C-business/online.py').read_text(encoding='utf-8'))
        ttls=[node.value.value for node in ast.walk(tree) if isinstance(node,ast.keyword) and node.arg=='ttl' and isinstance(node.value,ast.Constant)]
        if ttls!=[plan['ttl_seconds']]:raise ValueError('plan TTL does not match frozen runtime configuration')
        for port in (self.mqtt_port,self.http_port):
            with socket.socket() as probe:probe.bind(('127.0.0.1',port))

    def launch(self,name,command,env=None):
        log=(self.output/(name+'-'+str(len(self.history))+'.log')).open('x',encoding='utf-8');self.logs.append(log)
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        self.history.append((name,process));self.active[name]=process
        with (self.output/'processes.jsonl').open('a',encoding='utf-8') as receipt:
            receipt.write(json.dumps(dict(name=name,pid=process.pid,utc=datetime.now(timezone.utc).isoformat()))+'\n')
            receipt.flush();os.fsync(receipt.fileno())
        return process

    def wait_ready(self,check,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.ensure_alive({'name':'startup'})
            if check():
                self.ensure_alive({'name':'startup'})
                return
            time.sleep(.1)
        raise TimeoutError('owned service readiness timeout')

    def api(self,route):
        request=urllib.request.Request(f'http://127.0.0.1:{self.http_port}'+route,headers={'Authorization':'Bearer '+self.token})
        try:
            with self.http.open(request,timeout=2) as response:return {'status':response.status,'body':json.load(response)}
        except urllib.error.HTTPError as exc:
            try:return {'status':exc.code,'body':json.load(exc)}
            finally:exc.close()
        except (OSError,ValueError):return {'status':None,'body':None}

    def broker_ready(self):
        # Socket reachability alone could be an unrelated racing listener.
        log=(self.output/'broker-0.log').read_text(encoding='utf-8',errors='replace').lower()
        owned_ready=f'opening ipv4 listen socket on port {self.mqtt_port}.' in log and 'mosquitto version' in log and ' running' in log and 'error:' not in log
        if not owned_ready:return False
        import re
        version=re.search(r'mosquitto version (\S+) running',log)
        if self.runtime_versions and (not version or version[1]!=self.runtime_versions['broker_version']):raise ValueError('broker self-reported version differs from lock')
        with socket.socket() as sock:return sock.connect_ex(('127.0.0.1',self.mqtt_port))==0

    def start(self,output,plan):
        self.verify_revision(plan)
        from mqtt_closeout_evidence import runtime_lock
        if not self.runtime_versions or runtime_lock(ROOT,self.broker,self.runtime_versions['broker_version'])!=self.runtime_versions:
            raise ValueError('runtime changed since preflight')
        self.output=Path(output).resolve();self.plan=plan;self.job=create_job()
        receipt=dict(revision=plan['revision'],broker_sha256=hashlib.sha256(self.broker.read_bytes()).hexdigest(),
                     broker_version=None,python=sys.version,paho_mqtt=importlib.metadata.version('paho-mqtt'),
                     mqtt_port=self.mqtt_port,http_port=self.http_port,
                     origin='simulation',job_owned=True)
        (self.output/'runtime.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        (self.output/'runtime-lock.json').write_text(json.dumps(self.runtime_versions,indent=2),encoding='utf-8')
        config=self.output/'broker.conf'
        config.write_text(f'listener {self.mqtt_port} 127.0.0.1\nallow_anonymous true\npersistence false\n',encoding='utf-8')
        # Windows background mode may otherwise emit no startup log. Readiness
        # deliberately requires this owned log as well as the loopback socket.
        self.launch('broker',[str(self.broker),'-c',str(config),'-v'])
        self.wait_ready(self.broker_ready)
        receipt['broker_version']=self.runtime_versions['broker_version']
        (self.output/'runtime.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        self.cli=ROOT/'spikes/SP-02/src/cli.py'
        self.launch('subscriber',[sys.executable,str(self.cli),'subscribe','--device-id','demo01','--directory',str(self.output),
                                  '--port',str(self.mqtt_port),'--seconds',str(plan['total_planned_seconds']+180),'--timing-evidence'])
        self.wait_ready(lambda:any('READY' in path.read_text(encoding='utf-8') for path in self.output.glob('subscriber-*.log')))
        # Journal initialization is owned and explicit; no existing database can be reused.
        sys.path.insert(0,str(self.cli.parent));sys.path.insert(0,str(ROOT))
        from core import Journal
        Journal(self.output/'journal.sqlite').close()
        self.env=os.environ.copy()
        self.env.update(AQUAGUARD_RUNTIME='mqtt',AQUAGUARD_HOST='127.0.0.1',AQUAGUARD_DEVICE_ID='demo01',AQUAGUARD_PORT=str(self.http_port),
                        AQUAGUARD_DB=str(self.output/'business.sqlite'),AQUAGUARD_MQTT_JOURNAL=str(self.output/'journal.sqlite'),
                        AQUAGUARD_MQTT_TIMING=str(self.output/'consumer-timings.jsonl'),
                        AQUAGUARD_C_TOKEN=self.token,AQUAGUARD_C_CURSOR_KEY=uuid4().hex+uuid4().hex)
        self.launch('edge',[sys.executable,'-m','edge'],self.env)
        self.wait_ready(lambda:(self.api('/health').get('body') or {}).get('status')=='ok')

    def publisher(self,stage,*,duplicate=False,retired=False):
        from core import sample
        self.stop_one('publisher')
        directory=self.output/(stage['name']+'-publisher');directory.mkdir()
        duration=self.plan['total_planned_seconds']
        rows=[]
        for tick in range(math.ceil(duration)+1):
            current=[sample(self.seq+tick,sensor,stage['boot'],device_id='demo01') for sensor in ('flow','water','presence')]
            current[1]['value']['wet']=True
            rows.extend(current)
            if tick==0 and duplicate:rows.extend(self.last_rows)
            if tick==0 and retired:
                # A new identity from the retired boot must reach quarantine;
                # repeating an existing identity would only test Journal dedup.
                rows.extend(sample(self.seq,sensor,self.last_rows[0]['boot_id'],device_id='demo01') for sensor in ('flow','water','presence'))
        # Replay the first batch, not an unsent tail from the prebuilt manifest.
        self.seq+=math.ceil(duration)+1;self.last_rows=rows[:3]
        (directory/'manifest.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
        self.publisher_stop_file=directory/'stop.request'
        self.launch('publisher',[sys.executable,str(self.cli),'publish','--device-id','demo01','--directory',str(directory),
                                 '--port',str(self.mqtt_port),'--interval',str(1/3),'--timing-evidence','--stop-file',str(self.publisher_stop_file)])

    def enter(self,stage):
        from mqtt_phase_evidence import capture
        self.phase_before=capture(self.output/'business.sqlite',self.output/'journal.sqlite')
        name=stage['name']
        if name=='startup':
            self.publisher(stage)
            def consumer_ready():
                with closing(sqlite3.connect((self.output/'business.sqlite').as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
                    return db.execute('SELECT cursor FROM mqtt_consumer WHERE singleton=1').fetchone() is not None
            self.wait_ready(consumer_ready)
            return {'ready':True,'checks':['broker_listening','subscriber_READY','edge_health_ok','consumer_initialized']}
        elif name=='publisher_stop':self.stop_one('publisher')
        elif name=='resume_duplicate':self.publisher(stage,duplicate=True)
        elif name=='edge_restart':
            self.stop_one('edge');self.launch('edge',[sys.executable,'-m','edge'],self.env)
            self.wait_ready(lambda:self.api('/health')['status']==200)
            return {'ready':True,'checks':['restarted_edge_health_200']}
        elif name=='new_boot':self.publisher(stage,retired=True)
        elif name=='shutdown':
            self.stop_one('publisher')
            self.wait_ready(self.drained)
            self.stop()

    def ensure_alive(self,stage):
        if stage['name']=='shutdown':return
        for name,process in self.active.items():
            if process.poll() is not None:raise RuntimeError('owned '+name+' exited before planned stop')

    def observe(self,stage):
        from mqtt_capacity_snapshot import snapshot
        from mqtt_runtime_observation import process_resources,os_clocks
        from mqtt_closeout_evidence import checkpoint_sizes
        return dict(live=None if stage['name']=='shutdown' else self.api('/api/devices/demo01/live'),
                    capacity=snapshot(self.output/'journal.sqlite',self.output/'business.sqlite'),
                    checkpoints=checkpoint_sizes(self.output/'business.sqlite.checkpoints'),
                    resources=[dict(name=name,pid=process.pid,**process_resources(process)) for name,process in self.active.items()],
                    os_clock=os_clocks())

    def drained(self):
        from mqtt_closeout_evidence import consumption_latency
        from mqtt_ack_summary import summarize
        from mqtt_capacity_snapshot import snapshot
        latency=consumption_latency(list(self.output.glob('*-publisher/publisher-timings.jsonl')),self.output/'consumer-timings.jsonl')
        ack=summarize(self.output/'subscriber-timings.jsonl')
        return (latency['status']=='AVAILABLE' and ack['status']=='AVAILABLE' and ack['records']>=latency['valid_publications']
                and snapshot(self.output/'journal.sqlite',self.output/'business.sqlite')['pending_eligible_attempts']==0)

    def assert_phase(self,stage,samples):
        from mqtt_phase_evidence import capture,evaluate
        after=capture(self.output/'business.sqlite',self.output/'journal.sqlite')
        evidence=dict(before=self.phase_before,after=after)
        value=evaluate(stage,self.phase_before,after,samples)
        value['evidence']=evidence
        return value

    def stop_one(self,name):
        process=self.active.get(name)
        if process is None:return
        if name=='publisher' and self.publisher_stop_file is not None and process.poll() is None:
            self.publisher_stop_file.touch(exist_ok=True)
            try:process.wait(timeout=12)
            except subprocess.TimeoutExpired:pass
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        if process.poll() is None:raise RuntimeError('owned child exit not confirmed')
        del self.active[name]

    def stop(self):
        failures=[]
        for name in reversed(list(self.active)):
            try:self.stop_one(name)
            except (OSError,subprocess.TimeoutExpired,RuntimeError):failures.append(name)
        for log in self.logs:log.close()
        children=[dict(name=name,pid=process.pid,exit_code=process.poll(),exit_confirmed=process.poll() is not None) for name,process in self.history]
        return dict(all_exited=not failures and all(child['exit_confirmed'] for child in children),children=children,failures=failures)

    def exit_checks(self):
        checks=database_exit_checks(self.output/'business.sqlite',self.output/'journal.sqlite')
        ports={}
        for name,port in (('mqtt',self.mqtt_port),('http',self.http_port)):
            with socket.socket() as probe:
                probe.settimeout(.5)
                ports[name]=probe.connect_ex(('127.0.0.1',port))!=0
        checks['ports_closed']=ports
        from mqtt_ack_summary import summarize
        checks['ack_evidence']=summarize(self.output/'subscriber-timings.jsonl')
        from mqtt_closeout_evidence import checkpoint_inventory,consumption_latency
        checks['checkpoints']=checkpoint_inventory(self.output/'business.sqlite',self.output/'business.sqlite.checkpoints')
        checks['consumption_latency']=consumption_latency(list(self.output.glob('*-publisher/publisher-timings.jsonl')),self.output/'consumer-timings.jsonl')
        checks['ok']=(checks['ok'] and all(ports.values()) and checks['ack_evidence']['status']=='AVAILABLE'
                      and checks['checkpoints']['ok'] and checks['consumption_latency']['status']=='AVAILABLE')
        return checks
