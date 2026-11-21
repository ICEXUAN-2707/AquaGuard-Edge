"""Explicit Windows MQTT execution with a temporary thread-scoped power request.

Does not change the power plan or prevent explicit user sleep. Evidence gates
remain in mqtt_protocol_runner; the request is released on every normal exit.
"""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path


@contextmanager
def system_required(set_state=None):
    if set_state is None:
        if os.name!='nt':raise OSError('Windows power request required')
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        set_state=api.SetThreadExecutionState
        set_state.argtypes=[wintypes.DWORD];set_state.restype=wintypes.DWORD
    previous=set_state(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if not previous:raise OSError('system-required power request failed')
    receipt={'requested':True,'restored':False,'previous_state':previous,
             'scope':'thread lifetime; no display or persistent power-plan change'}
    try:yield receipt
    finally:
        receipt['restored']=bool(set_state(previous|0x80000000))
        if not receipt['restored']:raise OSError('power request restore failed')


def main():
    import argparse
    from mqtt_protocol_runner import execute,validate_plan
    from mqtt_local_backend import LocalBackend
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--broker',type=Path,required=True)
    parser.add_argument('--mqtt-port',type=int,default=18893);parser.add_argument('--http-port',type=int,default=8055)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--allow-long-run',action='store_true')
    args=parser.parse_args();plan=json.loads(args.plan.read_text(encoding='utf-8'))
    duration=validate_plan(plan)
    if not args.execute or (duration>60 and not args.allow_long_run):parser.error('explicit execution and duration authorization required')
    backend=LocalBackend(args.broker,args.mqtt_port,args.http_port);backend.preflight(plan)
    receipt={}
    try:
        with system_required() as receipt:
            receipt['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            value=execute(plan,backend,args.output,allow_execution=True,allow_long_run=args.allow_long_run)
    finally:
        if args.output.is_dir() and receipt:
            (args.output/'power-request.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(value));return 0 if value['execution_status']=='COMPLETED' else 1


if __name__=='__main__':raise SystemExit(main())
