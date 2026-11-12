"""Owned local simulation wall-clock observation; never deletes business data."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


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
    files = list(directory.rglob('*'))
    checkpoints = [p for p in files if p.is_file() and '.checkpoints' in str(p.relative_to(directory))]
    sqlite_files = [p for p in files if p.is_file() and (p.name.endswith('.sqlite') or p.name.endswith(('.sqlite-wal', '.sqlite-shm')))]
    return dict(sqlite_bytes=sum(p.stat().st_size for p in sqlite_files),
                checkpoint_bytes=sum(p.stat().st_size for p in checkpoints), checkpoint_files=len(checkpoints))


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
    args=parser.parse_args()
    if args.seconds<45 or args.interval<1 or not 1<=args.port<=65535:
        parser.error('seconds >=45, interval >=1 and valid port required')
    with socket.socket() as probe: probe.bind(('127.0.0.1',args.port))
    out=args.directory.resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    env.update(AQUAGUARD_RUNTIME='simulation',AQUAGUARD_DEVICE_ID='demo01',AQUAGUARD_HOST='127.0.0.1',
               AQUAGUARD_PORT=str(args.port),AQUAGUARD_DB=str(out/'business.sqlite'),
               AQUAGUARD_C_TOKEN=secrets.token_hex(24),AQUAGUARD_C_CURSOR_KEY=secrets.token_hex(32))
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    metadata=dict(revision=revision,tracked_changes=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()),
                  source='simulation',mode='wall_clock',requested_seconds=args.seconds,interval=args.interval,
                  python=sys.version,cloud_accepted=False)
    (out/'run.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    def request(route):
        req=urllib.request.Request(f'http://127.0.0.1:{args.port}'+route,headers={'Authorization':'Bearer '+env['AQUAGUARD_C_TOKEN']})
        try:
            with urllib.request.urlopen(req,timeout=3) as response:
                data=json.load(response)
                return {'status':response.status,'captured_at':data.get('captured_at')}
        except urllib.error.HTTPError as exc:return {'status':exc.code}
        except (OSError,ValueError):return {'status':None}
    samples=[];started=time.monotonic();failure=None;process=None
    try:
        with (out/'service.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-m','edge'],cwd=ROOT,env=env,stdout=log,stderr=log)
            with (out/'samples.jsonl').open('w',encoding='utf-8') as stream:
                while True:
                    elapsed=time.monotonic()-started
                    sample=dict(elapsed_sec=round(elapsed,3),**tree_memory(process.pid),
                                process_alive=process.poll() is None,health=request('/health'),
                                live=request('/api/devices/demo01/live'),**storage_snapshot(out))
                    try:sample['database']=database_snapshot(out/'business.sqlite')
                    except sqlite3.Error as exc:sample['database']={'error_type':type(exc).__name__}
                    samples.append(sample);stream.write(json.dumps(sample)+'\n');stream.flush()
                    if not sample['process_alive']:raise RuntimeError('owned service exited during observation')
                    if elapsed>=args.seconds:break
                    time.sleep(min(args.interval,args.seconds-elapsed))
    except BaseException as exc:
        failure=type(exc).__name__
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
    try:final=database_snapshot(out/'business.sqlite',final=True)
    except sqlite3.Error as exc:final={'error_type':type(exc).__name__}
    steady=[s for s in samples if s['elapsed_sec']>=45]
    good=bool(steady) and all(s['health']['status']==200 and s['live']['status']==200 for s in steady)
    passed=not failure and good and final.get('integrity')=='ok' and final.get('duplicate_open_groups')==0
    result=dict(status='PASS' if passed else 'FAIL',failure_type=failure,
                observed_seconds=round(time.monotonic()-started,3),samples=len(samples),
                steady_samples=len(steady),steady_api_available=good,database=final,
                owned_process_exited=process is not None and process.poll() is not None,
                rss_peak_bytes=max((s['rss_bytes'] for s in samples if s['rss_bytes'] is not None),default=None),
                observed_growth_bytes_per_hour={key:growth(samples,key) for key in ('rss_bytes','sqlite_bytes','checkpoint_bytes')},
                note='Endpoint growth is descriptive, not a leak verdict or long-term capacity guarantee; startup first 45s excluded from API gate. Forced termination is not graceful shutdown acceptance.')
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result));return 0 if passed else 1


if __name__=='__main__':sys.exit(main())
