"""Summarize subscriber-local commit/ACK submission, preserving missing evidence."""
import json
import math
from pathlib import Path


def summarize(path):
    result=dict(scope='subscriber_local_commit_ack_submission',records=0,completed=0,incomplete=0,invalid=0,
                broker_confirmation='NOT_MEASURED',acceptance_passed=False,
                note='Latency describes completed valid records only; all incomplete/invalid records remain counted. Not publisher-to-business or cloud latency.')
    values={name:[] for name in ('receive_to_commit_seconds','commit_to_ack_submit_seconds','receive_to_ack_submit_seconds')}
    try:
        with Path(path).open(encoding='utf-8') as stream:
            for line in stream:
                result['records']+=1
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('object required')
                    if row.get('commit_returned') is not True or row.get('ack_submitted') is not True:
                        result['incomplete']+=1;continue
                    durations=[row[name] for name in values]
                    if row.get('scope')!='subscriber_commit_ack_submission' or row.get('broker_ack_confirmed') is not None:
                        raise ValueError('wrong evidence scope')
                    if any(type(value) not in (int,float) or not math.isfinite(value) or value<0 for value in durations):
                        raise ValueError('invalid latency')
                    if not math.isclose(durations[0]+durations[1],durations[2],rel_tol=1e-6,abs_tol=1e-6):
                        raise ValueError('inconsistent latency components')
                    for name,value in zip(values,durations):values[name].append(value)
                    result['completed']+=1
                except (ValueError,KeyError,TypeError):result['invalid']+=1
    except (OSError,UnicodeError) as exc:
        result.update(status='INCOMPLETE',error_type=type(exc).__name__);return result
    for name,items in values.items():
        ordered=sorted(items)
        result[name]=dict(samples=len(items),p50=ordered[math.ceil(len(items)*.5)-1] if items else None,
                          p95=ordered[math.ceil(len(items)*.95)-1] if items else None,max=max(items) if items else None)
    result['status']='AVAILABLE' if result['records'] and not result['incomplete'] and not result['invalid'] else 'INCOMPLETE'
    return result
