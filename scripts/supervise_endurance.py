"""Task Scheduler entrypoint: durable heartbeat and child exit receipt."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


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
    try:
        atomic_json(receipt,record)
        with (out.parent/(out.name+'.supervisor.log')).open('w',encoding='utf-8') as log:
            command=[sys.executable,str(Path(__file__).with_name('runtime_endurance.py')),
                     '--directory',str(out),'--seconds',str(args.seconds),'--interval',str(args.interval),
                     '--port',str(args.port),'--keep-awake']
            process=subprocess.Popen(command,cwd=Path(__file__).resolve().parents[1],stdout=log,stderr=log)
            record.update(phase='running',child_pid=process.pid)
            while True:
                record['heartbeat_at']=datetime.now(timezone.utc).isoformat()
                atomic_json(receipt,record)
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
