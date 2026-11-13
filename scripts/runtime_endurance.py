"""Owned local simulation wall-clock observation; never deletes business data."""
import argparse
import ctypes
import faulthandler
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import secrets
import socket
import stat
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def host_clocks():
    if os.name!='nt':return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetTickCount64.restype=ctypes.c_ulonglong
    query=kernel.QueryUnbiasedInterruptTime
    query.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)]
    active=ctypes.c_ulonglong()
    if not query(ctypes.byref(active)):return None
    return {'uptime_seconds':kernel.GetTickCount64()/1000,'awake_seconds':active.value/10000000}


def suspend_delta(previous,current):
    if previous is None or current is None:return None
    return max(0,(current['uptime_seconds']-previous['uptime_seconds'])-(current['awake_seconds']-previous['awake_seconds']))


def keep_awake(enabled):
    """Thread-scoped system sleep request; never changes display/power settings."""
    if not enabled:return
    if os.name!='nt':raise RuntimeError('keep-awake requires Windows')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=kernel.SetThreadExecutionState
    function.argtypes=[wintypes.DWORD];function.restype=wintypes.DWORD
    if not function(0x80000001):raise OSError('system awake request failed')


def release_awake(enabled):
    if enabled and os.name=='nt':
        ctypes.WinDLL('kernel32').SetThreadExecutionState(0x80000000)


def sampling_coverage(samples,interval):
    gaps=[b['elapsed_sec']-a['elapsed_sec'] for a,b in zip(samples,samples[1:])]
    limit=max(5,interval*2)
    return {'max_sample_gap_seconds':max(gaps,default=0), 'gap_limit_seconds':limit,
            'coverage_valid':len(samples)>=2 and all(gap<=limit for gap in gaps)}


def process_tree(root_pid):
    """Include Windows venv launcher children, using Toolhelp without commands."""
    if os.name != 'nt':
        return [root_pid]
    class Entry(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                  ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                  ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
                  ('exe',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==ctypes.c_void_p(-1).value:
        raise OSError('process snapshot unavailable')
    parents={}
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        valid=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while valid:
            parents[entry.pid]=entry.parent
            valid=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    selected={root_pid}
    while True:
        expanded=selected|{pid for pid,parent in parents.items() if parent in selected}
        if expanded==selected:return sorted(selected)
        selected=expanded


def tree_memory(pid):
    pids=process_tree(pid)
    values=[memory_bytes(child) for child in pids]
    return dict(rss_bytes=sum(values) if all(v is not None for v in values) else None,
                process_count=len(pids))


def memory_bytes(pid):
    if os.name != 'nt':
        return None  # Explicitly unavailable; no invented zero.
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak_rss', 'rss', 'peak_pool', 'pool',
                                               'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    query = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        return None
    try:
        value = Counters(); value.cb = ctypes.sizeof(value)
        return value.rss if query(handle, ctypes.byref(value), value.cb) else None
    finally:
        kernel.CloseHandle(handle)


def storage_snapshot(directory):
    result=dict(sqlite_bytes=0,checkpoint_bytes=0,checkpoint_files=0,transient_files_disappeared=0)
    for path in directory.rglob('*'):
        checkpoint='.checkpoints' in str(path.relative_to(directory)) and path.suffix=='.json'
        database=path.name.endswith(('.sqlite','.sqlite-wal','.sqlite-shm'))
        if not checkpoint and not database:continue
        try:info=path.stat()
        except FileNotFoundError:
            result['transient_files_disappeared']+=1
            continue  # Atomic rename/WAL cleanup can race an observational scan.
        if not stat.S_ISREG(info.st_mode):continue
        if checkpoint:
            result['checkpoint_bytes']+=info.st_size;result['checkpoint_files']+=1
        if database:result['sqlite_bytes']+=info.st_size
    return result


def database_snapshot(path, final=False):
    if not path.exists():
        return {'available': False}
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result={'available':True,'counts':{name:db.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                for name in ('events','transitions','outbox') if name in tables}}
        if final:
            result['integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]
            if 'events' in tables:
                result['duplicate_open_groups']=len(db.execute("SELECT device_id,event_type FROM events WHERE lifecycle='OPEN' GROUP BY device_id,event_type HAVING count(*)>1").fetchall())
        return result


def growth(samples, key):
    valid=[s for s in samples if isinstance(s.get(key),(int,float))]
    if len(valid)<2 or valid[-1]['elapsed_sec']<=valid[0]['elapsed_sec']:
        return None
    return (valid[-1][key]-valid[0][key])*3600/(valid[-1]['elapsed_sec']-valid[0]['elapsed_sec'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=3600)
    parser.add_argument('--interval',type=float,default=15)
    parser.add_argument('--port',type=int,default=8037)
    parser.add_argument('--keep-awake',action='store_true',help='Windows process-scoped sleep inhibition for this observation only')
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or not math.isfinite(args.interval) or args.seconds<45 or args.interval<1 or not 1<=args.port<=65535:
        parser.error('seconds >=45, interval >=1 and valid port required')
    with socket.socket() as probe: probe.bind(('127.0.0.1',args.port))
    out=args.directory.resolve();out.mkdir(parents=True,exist_ok=False)
    def stage(name):
        target=out/'progress.json';temporary=out/'progress.json.tmp'
        temporary.write_text(json.dumps({'stage':name,'utc':datetime.now(timezone.utc).isoformat(),'observer_pid':os.getpid()}),encoding='utf-8')
        os.replace(temporary,target)
    # Local stack-only diagnostics: no variables, environment, token or payloads.
    stack_log=(out/'observer-stacks.log').open('w',encoding='utf-8')
    faulthandler.dump_traceback_later(60,repeat=True,file=stack_log)
    stage('metadata')
    env=os.environ.copy()
    env.update(AQUAGUARD_RUNTIME='simulation',AQUAGUARD_DEVICE_ID='demo01',AQUAGUARD_HOST='127.0.0.1',
               AQUAGUARD_PORT=str(args.port),AQUAGUARD_DB=str(out/'business.sqlite'),
               AQUAGUARD_C_TOKEN=secrets.token_hex(24),AQUAGUARD_C_CURSOR_KEY=secrets.token_hex(32))
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    metadata=dict(revision=revision,tracked_changes=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()),
                  source='simulation',mode='wall_clock',requested_seconds=args.seconds,interval=args.interval,
                  python=sys.version,cloud_accepted=False,keep_awake_requested=args.keep_awake)
    (out/'run.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    def request(route):
        began=time.monotonic()
        req=urllib.request.Request(f'http://127.0.0.1:{args.port}'+route,headers={'Authorization':'Bearer '+env['AQUAGUARD_C_TOKEN']})
        try:
            with urllib.request.urlopen(req,timeout=3) as response:
                data=json.load(response)
                return {'status':response.status,'captured_at':data.get('captured_at'),'request_seconds':time.monotonic()-began,
                        **({'diagnostics':data} if route.startswith('/api/runtime/diagnostics') else {})}
        except urllib.error.HTTPError as exc:return {'status':exc.code,'request_seconds':time.monotonic()-began}
        except (OSError,ValueError) as exc:return {'status':None,'request_seconds':time.monotonic()-began,'error_type':type(exc).__name__}
    samples=[];started=time.monotonic();failure=None;process=None;previous=None;previous_host=None
    try:
        keep_awake(args.keep_awake)
        with (out/'service.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-m','edge'],cwd=ROOT,env=env,stdout=log,stderr=log)
            with (out/'samples.jsonl').open('w',encoding='utf-8') as stream:
                while True:
                    elapsed=time.monotonic()-started
                    sample_utc=datetime.now(timezone.utc).isoformat()
                    stage('host_clocks')
                    host=host_clocks()
                    stage('process_memory')
                    memory=tree_memory(process.pid)
                    stage('health_http');health=request('/health')
                    stage('live_http');live=request('/api/devices/demo01/live')
                    stage('diagnostics_http');diagnostic=request('/api/runtime/diagnostics')
                    stage('storage_scan');storage=storage_snapshot(out)
                    sample=dict(elapsed_sec=round(elapsed,3),**memory,
                                host_clocks=host,estimated_suspend_seconds=suspend_delta(previous_host,host),
                                utc=sample_utc,collection_finished_at=datetime.now(timezone.utc).isoformat(),
                                collection_seconds=time.monotonic()-started-elapsed,
                                sample_gap_seconds=None if previous is None else elapsed-previous,
                                sampling_lag_seconds=None if previous is None else max(0,elapsed-previous-args.interval),
                                process_alive=process.poll() is None,health=health,
                                live=live,runtime=diagnostic,**storage)
                    previous=elapsed
                    previous_host=host
                    stage('database_scan')
                    try:sample['database']=database_snapshot(out/'business.sqlite')
                    except sqlite3.Error as exc:sample['database']={'error_type':type(exc).__name__}
                    samples.append(sample);stream.write(json.dumps(sample)+'\n');stream.flush()
                    stage('sleep')
                    faulthandler.cancel_dump_traceback_later()
                    faulthandler.dump_traceback_later(max(60,args.interval*2),repeat=True,file=stack_log)
                    if not sample['process_alive']:raise RuntimeError('owned service exited during observation')
                    if elapsed>=args.seconds:break
                    time.sleep(min(args.interval,args.seconds-elapsed))
    except BaseException as exc:
        failure=type(exc).__name__
    finally:
        release_awake(args.keep_awake)
        if process is not None and process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,check=False)
            else:
                process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
    try:final=database_snapshot(out/'business.sqlite',final=True)
    except sqlite3.Error as exc:final={'error_type':type(exc).__name__}
    steady=[s for s in samples if s['elapsed_sec']>=45]
    good=bool(steady) and all(s['health']['status']==200 and s['live']['status']==200 for s in steady)
    with socket.socket() as probe:
        probe.settimeout(1)
        port_closed=probe.connect_ex(('127.0.0.1',args.port))!=0
    coverage=sampling_coverage(samples,args.interval)
    passed=not failure and good and coverage['coverage_valid'] and port_closed and final.get('integrity')=='ok' and final.get('duplicate_open_groups')==0
    result=dict(status='PASS' if passed else 'FAIL',failure_type=failure,
                observed_seconds=round(time.monotonic()-started,3),samples=len(samples),
                steady_samples=len(steady),steady_api_available=good,database=final,
                owned_process_exited=process is not None and process.poll() is not None,
                port_closed=port_closed,
                sampling_coverage=coverage,
                rss_peak_bytes=max((s['rss_bytes'] for s in samples if s['rss_bytes'] is not None),default=None),
                observed_growth_bytes_per_hour={key:growth(samples,key) for key in ('rss_bytes','sqlite_bytes','checkpoint_bytes')},
                steady_growth_bytes_per_hour={key:growth(steady,key) for key in ('rss_bytes','sqlite_bytes','checkpoint_bytes')},
                note='Endpoint growth is descriptive, not a leak verdict or long-term capacity guarantee; startup first 45s excluded from API gate. Forced termination is not graceful shutdown acceptance.')
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    stage('finished')
    faulthandler.cancel_dump_traceback_later();stack_log.close()
    print(json.dumps(result));return 0 if passed else 1


if __name__=='__main__':sys.exit(main())
