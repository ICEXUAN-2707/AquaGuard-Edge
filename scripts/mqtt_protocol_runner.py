"""Explicit local MQTT protocol execution; never a long-run acceptance verdict."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time

PHASES=('startup','continuous','publisher_stop','resume_duplicate','edge_restart','new_boot','shutdown')


def validate_plan(plan):
    if plan.get('schema_version')!=1 or plan.get('status')!='PREPARED':raise ValueError('prepared v1 plan required')
    if plan.get('host')!='127.0.0.1' or plan.get('origin')!='simulation' or plan.get('device_id')!='demo01':
        raise ValueError('loopback simulation demo01 only')
    if not re.fullmatch('[0-9a-f]{40}',plan.get('revision','')):raise ValueError('fixed revision required')
    stages=plan.get('stages',[])
    if tuple(stage.get('name') for stage in stages)!=PHASES:raise ValueError('ordered protocol phases required')
    offset=0
    for stage in stages:
        start,end=stage.get('planned_start_seconds'),stage.get('planned_end_seconds')
        if any(type(value) not in (int,float) or not math.isfinite(value) for value in (start,end)):
            raise ValueError('finite phase bounds required')
        if start!=offset or not 0<end-start<=86400:raise ValueError('contiguous bounded phase windows required')
        offset=end
    interval=plan.get('sample_interval_seconds')
    ttl=plan.get('ttl_seconds')
    if any(type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=3600 for value in (interval,ttl)) or interval<1:
        raise ValueError('bounded interval and TTL required')
    if stages[2]['planned_end_seconds']-stages[2]['planned_start_seconds']<=ttl:
        raise ValueError('stop phase must exceed TTL')
    original=stages[0].get('boot');new=stages[5].get('boot')
    if not all(isinstance(value,str) and re.fullmatch('[0-9a-f]{32}',value) for value in (original,new)):
        raise ValueError('fixed boot identities required')
    if any(stage.get('boot')!=original for stage in stages[:5]) or new==original or stages[6].get('boot') is not None:
        raise ValueError('boot recovery contract invalid')
    if plan.get('total_planned_seconds')!=offset or offset>86400:raise ValueError('invalid total duration')
    return offset


def execute(plan,backend,output,*,allow_execution=False,allow_long_run=False,clock=time.monotonic,sleep=time.sleep):
    total=validate_plan(plan)
    if not allow_execution:raise ValueError('execution is disabled without explicit --execute')
    if total>60 and not allow_long_run:raise ValueError('long execution requires --allow-long-run')
    backend.preflight(plan)  # No output or process launch before validation succeeds.
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    result=dict(execution_status='FAILED',acceptance_passed=False,long_run_acceptance=False,
                completed_phases=[],phase_assertions={},error_type=None,cleanup=None,exit_checks=None,
                note='Execution completion is not availability, fault assertions, latency or capacity acceptance.')
    started=clock()
    with (output/'phases.jsonl').open('x',encoding='utf-8') as phases, (output/'samples.jsonl').open('x',encoding='utf-8') as samples:
        def event(stage,state,**details):
            import os
            phases.write(json.dumps(dict(phase=stage['name'],state=state,utc=datetime.now(timezone.utc).isoformat(),
                                         elapsed_seconds=clock()-started,**details))+'\n')
            phases.flush();os.fsync(phases.fileno())
        try:
            for stage in plan['stages']:
                event(stage,'ENTERED',planned_start_seconds=stage['planned_start_seconds'])
                phase_start=clock();duration=stage['planned_end_seconds']-stage['planned_start_seconds']
                if stage['name']=='startup':backend.start(output,plan)
                readiness=backend.enter(stage)
                if stage['name'] in ('startup','edge_restart'):
                    if not readiness or not readiness.get('ready'):raise RuntimeError('explicit READY evidence required')
                    event(stage,'READY',checks=readiness.get('checks',[]))
                if clock()-phase_start>=duration:raise TimeoutError('phase actions exceeded planned window')
                sample_count=0;phase_samples=[]
                while clock()-phase_start<duration:
                    backend.ensure_alive(stage)
                    observed=clock()
                    observation=backend.observe(stage)
                    phase_samples.append(observation)
                    samples.write(json.dumps(dict(phase=stage['name'],elapsed_seconds=observed-started,
                                                  collection_seconds=clock()-observed,**observation))+'\n');samples.flush()
                    sample_count+=1
                    # No historical backfill after an observer/host gap.
                    remaining=duration-(clock()-phase_start)
                    if remaining>0:sleep(min(plan['sample_interval_seconds'],remaining))
                actual=clock()-phase_start
                assertions=backend.assert_phase(stage,phase_samples)
                result['phase_assertions'][stage['name']]=assertions
                event(stage,'ASSERTED',assertions=assertions)
                if assertions.get('status')!='SATISFIED':raise RuntimeError('phase assertions violated or incomplete')
                event(stage,'FINISHED',actual_duration_seconds=actual,samples=sample_count,assertions_status=assertions['status'])
                result['completed_phases'].append(stage['name'])
            result['execution_status']='COMPLETED'
        except BaseException as exc:
            result['error_type']=type(exc).__name__
            if len(result['completed_phases'])<len(plan['stages']):
                event(plan['stages'][len(result['completed_phases'])],'FAILED',error_type=type(exc).__name__)
        finally:
            try:
                result['cleanup']=backend.stop()
                if not result['cleanup'].get('all_exited'):result['execution_status']='FAILED'
            except BaseException as exc:
                result.update(execution_status='FAILED',cleanup_error_type=type(exc).__name__)
            try:
                if result['cleanup'] and result['cleanup'].get('all_exited'):
                    result['exit_checks']=backend.exit_checks()
                else:
                    result['exit_checks']={'ok':False,'status':'SKIPPED_UNCONFIRMED_PROCESS_EXIT'}
                if not result['exit_checks'].get('ok'):result['execution_status']='FAILED'
            except BaseException as exc:
                result.update(execution_status='FAILED',exit_check_error_type=type(exc).__name__)
            result['elapsed_seconds']=clock()-started
            temporary=output/'result.json.tmp'
            temporary.write_text(json.dumps(result,indent=2),encoding='utf-8');temporary.replace(output/'result.json')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--broker',required=True,type=Path)
    parser.add_argument('--mqtt-port',type=int,default=18887);parser.add_argument('--http-port',type=int,default=8051)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--allow-long-run',action='store_true')
    args=parser.parse_args()
    from mqtt_local_backend import LocalBackend
    value=execute(json.loads(args.plan.read_text(encoding='utf-8')),LocalBackend(args.broker,args.mqtt_port,args.http_port),
                  args.output,allow_execution=args.execute,allow_long_run=args.allow_long_run)
    print(json.dumps(value));raise SystemExit(0 if value['execution_status']=='COMPLETED' else 1)
