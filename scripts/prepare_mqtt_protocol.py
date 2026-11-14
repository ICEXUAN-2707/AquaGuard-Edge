"""Prepare an immutable local MQTT phase plan; this entrypoint cannot execute it."""
import argparse
import json
import math
from pathlib import Path
import re
from uuid import uuid4


def prepare(output,*,revision,ttl,stop_seconds,continuous_seconds=3600,interval=15):
    if not isinstance(revision,str) or not re.fullmatch(r'[0-9a-f]{40}',revision):
        raise ValueError('fixed full Git commit SHA required')
    for value in (ttl,stop_seconds,continuous_seconds,interval):
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
            raise ValueError('finite positive timing values required')
    if stop_seconds<=ttl:raise ValueError('publisher-stop phase must exceed configured TTL')
    if interval>continuous_seconds:raise ValueError('sampling interval exceeds continuous phase')
    run_id=uuid4().hex;boot=uuid4().hex;new_boot=uuid4().hex
    stages=[];offset=0
    definitions=[
        ('startup',45,'original','subscriber READY and public health ready; establish first feature window'),
        ('continuous',continuous_seconds,'original','wall-clock simulation input; normal availability denominator'),
        ('publisher_stop',stop_seconds,'original','no publisher; observe TTL expiry and UNKNOWN/rejection'),
        ('resume_duplicate',45,'original','resume same boot with controlled repeated identities; no repeated business side effects'),
        ('edge_restart',45,'original','restart owned edge only, preserve Journal/business DB and event identity'),
        ('new_boot',45,'new','new analysis window; inject a marked old-boot sample to check isolation'),
        ('shutdown',15,'none','stop owned input/processes; collect DB integrity, OPEN uniqueness and exit evidence'),
    ]
    for name,seconds,identity,expectation in definitions:
        stages.append(dict(name=name,planned_start_seconds=offset,planned_end_seconds=offset+seconds,
                           boot=boot if identity=='original' else new_boot if identity=='new' else None,
                           expectation=expectation))
        offset+=seconds
    plan=dict(schema_version=1,status='PREPARED',execution_enabled=False,acceptance_passed=False,
              run_id=run_id,revision=revision,origin='simulation',device_id='demo01',host='127.0.0.1',
              ttl_seconds=ttl,sample_interval_seconds=interval,stages=stages,
              total_planned_seconds=offset,
              unresolved=['Resolve and record loopback ports, broker path/hash/version and dependency lock before execution.',
                          'Verify TTL against the frozen runtime configuration; this plan does not inspect runtime config.',
                          'Implement owned-process backend, readiness gates, phase receipts and failure cleanup.',
                          'Collect per-process resources, OS pause evidence, business consumption lag and exit invariants.',
                          'Define final coverage/latency/capacity thresholds before execution; no thresholds imply no PASS.'],
              note='Offsets are a predeclared plan, not observed timestamps. A phase failure must remain in evidence; do not shift normal/fault denominators after failure.')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--ttl',required=True,type=float)
    parser.add_argument('--stop-seconds',required=True,type=float)
    parser.add_argument('--continuous-seconds',type=float,default=3600)
    parser.add_argument('--interval',type=float,default=15)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,revision=args.revision,ttl=args.ttl,stop_seconds=args.stop_seconds,
                             continuous_seconds=args.continuous_seconds,interval=args.interval),indent=2))
