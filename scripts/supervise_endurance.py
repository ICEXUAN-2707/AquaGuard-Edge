"""Task Scheduler entrypoint: durable heartbeat and child exit receipt."""
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--seconds',type=float,default=3600)
    parser.add_argument('--interval',type=float,default=15)
    parser.add_argument('--port',type=int,default=8049)
    args=parser.parse_args()
    out=args.directory.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    receipt=out.parent/(out.name+'.supervisor.json')
    if out.exists() or receipt.exists():raise FileExistsError('Use a new observation directory')
    record={'phase':'starting','supervisor_pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat(),
            'child_pid':None,'child_exit_code':None,'result_exists':False}
    process=None
    started=time.monotonic()
    try:
        atomic_json(receipt,record)
        job_handle=owned_process_job()
        record['kill_on_supervisor_exit']=job_handle is not None
        with (out.parent/(out.name+'.supervisor.log')).open('w',encoding='utf-8') as log:
            command=[sys.executable,str(Path(__file__).with_name('runtime_endurance.py')),
                     '--directory',str(out),'--seconds',str(args.seconds),'--interval',str(args.interval),
                     '--port',str(args.port),'--keep-awake']
            process=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[1],stdout=log,stderr=log)
            record.update(phase='running',child_pid=process.pid)
            while True:
                record['heartbeat_at']=datetime.now(timezone.utc).isoformat()
                atomic_json(receipt,record)
                if time.monotonic()-started>args.seconds+90:
                    raise TimeoutError('observation exceeded duration and cleanup allowance')
                try:code=process.wait(timeout=10);break
                except subprocess.TimeoutExpired:continue
            result=out/'result.json'
            record.update(phase='completed' if code==0 and result.is_file() else 'failed',
                          child_exit_code=code,result_exists=result.is_file())
            if result.is_file():record['observation_status']=json.loads(result.read_text(encoding='utf-8')).get('status')
    except BaseException as exc:
        record.update(phase='supervisor_error',error_type=type(exc).__name__)
        if process is not None and process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
            else:process.terminate()
            process.wait(timeout=15)
            record['child_exit_code']=process.returncode
    finally:
        record['finished_at']=datetime.now(timezone.utc).isoformat()
        record['child_exit_confirmed']=process is not None and process.poll() is not None
        atomic_json(receipt,record)
    return 0 if record['phase']=='completed' else 1


if __name__=='__main__':sys.exit(main())
