"""Explicit Python child supervision: durable heartbeat, resources and exit receipt."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import math


def owned_process_job():
    """Own self and future descendants; OS kills descendants if supervisor dies."""
    if os.name!='nt':return None
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
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise OSError('Cannot create owned process job')
    limits=Limits();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        kernel.CloseHandle(handle);raise OSError('Cannot configure owned process job')
    if not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle);raise OSError('Cannot bind supervisor process job')
    # Intentionally held until process exit; closing it early would kill self.
    return handle


def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def child_resources(process):
    """Observe the owned child by its retained Windows handle, never a reused PID."""
    if os.name!='nt':return {'available':False,'reason':'Windows handle metrics unavailable'}
    try:
        class Memory(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD),
                      *[(name,ctypes.c_size_t) for name in ('peak_rss','rss','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
        kernel.GetPriorityClass.argtypes=[wintypes.HANDLE];kernel.GetPriorityClass.restype=wintypes.DWORD
        kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
        kernel.GetProcessTimes.restype=wintypes.BOOL
        handle=wintypes.HANDLE(int(process._handle))
        memory=Memory();memory.cb=ctypes.sizeof(memory)
        created,exited,kernel_time,user_time=(wintypes.FILETIME() for _ in range(4))
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.cb):raise ctypes.WinError(ctypes.get_last_error())
        priority=kernel.GetPriorityClass(handle)
        if not priority or not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel_time),ctypes.byref(user_time)):
            raise ctypes.WinError(ctypes.get_last_error())
        ticks=lambda value:(value.dwHighDateTime<<32)|value.dwLowDateTime
        return {'available':True,'scope':'owned_direct_child','rss_bytes':memory.rss,'peak_rss_bytes':memory.peak_rss,
                'priority_class':priority,'creation_filetime':ticks(created),
                'cpu_seconds':(ticks(kernel_time)+ticks(user_time))/10000000}
    except (OSError,AttributeError,TypeError,ValueError) as exc:
        return {'available':False,'reason':type(exc).__name__}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--seconds',type=float,default=30,help='child timeout, not experiment duration')
    parser.add_argument('--script',required=True,type=Path,help='explicit Python entrypoint')
    parser.add_argument('--allow-long-run',action='store_true')
    parser.add_argument('--args-file',type=Path,help='JSON array of string arguments; alternative to remainder')
    parser.add_argument('script_args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or not 0<args.seconds<=86400:parser.error('timeout must be in (0, 86400]')
    if args.seconds>60 and not args.allow_long_run:parser.error('long execution requires --allow-long-run')
    script=args.script.resolve()
    if not script.is_file() or script.suffix.lower()!='.py':parser.error('existing Python script required')
    child_args=args.script_args[1:] if args.script_args[:1]==['--'] else args.script_args
    if args.args_file:
        if child_args:parser.error('use args-file or remainder, not both')
        child_args=json.loads(args.args_file.read_text(encoding='utf-8-sig'))
        if not isinstance(child_args,list) or any(not isinstance(value,str) or '\0' in value for value in child_args):
            parser.error('args-file must contain a JSON array of strings without NUL')
    out=args.directory.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    receipt=out.parent/(out.name+'.supervisor.json')
    log_path=out.parent/(out.name+'.supervisor.log')
    samples_path=out.parent/(out.name+'.supervisor.samples.jsonl')
    if out.exists() or receipt.exists() or log_path.exists() or samples_path.exists():raise FileExistsError('Use a new observation directory')
    # Exclusive directory reservation prevents two supervisors sharing receipts.
    out.mkdir(exist_ok=False)
    record={'phase':'starting','supervisor_pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat(),
            'child_pid':None,'child_exit_code':None,'script':str(script),'timeout_seconds':args.seconds,
            'acceptance_passed':False}
    process=None
    started=time.monotonic()
    try:
        atomic_json(receipt,record)
        job_handle=owned_process_job()
        record['kill_on_supervisor_exit']=job_handle is not None
        with log_path.open('x',encoding='utf-8') as log, samples_path.open('x',encoding='utf-8') as samples:
            command=[sys.executable,str(script),*child_args]
            process=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[1],stdout=log,stderr=log)
            record.update(phase='running',child_pid=process.pid)
            while True:
                record['heartbeat_at']=datetime.now(timezone.utc).isoformat()
                record['child_resources']=child_resources(process)
                samples.write(json.dumps({'utc':record['heartbeat_at'],'elapsed_seconds':time.monotonic()-started,
                                          'resources':record['child_resources']})+'\n')
                samples.flush();os.fsync(samples.fileno())
                atomic_json(receipt,record)
                remaining=args.seconds-(time.monotonic()-started)
                if remaining<=0:raise TimeoutError('child exceeded configured timeout')
                try:code=process.wait(timeout=min(10,remaining));break
                except subprocess.TimeoutExpired:continue
            record.update(phase='completed' if code==0 else 'failed',child_exit_code=code)
    except BaseException as exc:
        record.update(phase='supervisor_error',error_type=type(exc).__name__)
        if process is not None and process.poll() is None:
            try:
                if os.name=='nt':
                    killed=subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                    record['tree_cleanup_exit_code']=killed.returncode
                else:process.terminate()
                process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired) as cleanup:
                record['cleanup_error_type']=type(cleanup).__name__
                if process.poll() is None:
                    process.kill()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:record['cleanup_unconfirmed']=True
            record['child_exit_code']=process.poll()
    finally:
        record['finished_at']=datetime.now(timezone.utc).isoformat()
        record['child_exit_confirmed']=process is not None and process.poll() is not None
        atomic_json(receipt,record)
    return 0 if record['phase']=='completed' else 1


if __name__=='__main__':sys.exit(main())
