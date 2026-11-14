"""Durability boundary. Storage exceptions propagate without acknowledging."""
from core import normalize
import re
import time


def observation_topic(device_id):
    if not isinstance(device_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device_id):
        raise ValueError('invalid configured device identity')
    return f'prototype/aquaguard/{device_id}/observation'


def process_message(msg, journal, acknowledge, after_commit=lambda: None, *, device_id='prototype01', timing=None, clock=time.perf_counter):
    """Optional timings observe submission, never broker receipt or business ACK."""
    topic = observation_topic(device_id)
    started=clock() if timing is not None else None
    if timing is not None:
        timing.update(scope='subscriber_commit_ack_submission',mid=msg.mid,qos=msg.qos,
                      commit_returned=False,ack_submitted=False,broker_ack_confirmed=None,
                      started_monotonic=started)
    record = dict(topic=msg.topic, qos=msg.qos, retain=msg.retain, raw_hex=msg.payload.hex())
    try:
        if msg.topic != topic:
            raise ValueError('unexpected topic')
        if msg.retain:
            raise ValueError('retained observation rejected')
        row = normalize(msg.payload, device_id, 'simulation')
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        record.update(classification='invalid', error=str(exc))
        if timing is not None:timing['storage_started_monotonic']=clock()
        journal.reject(record)
    else:
        if timing is not None:
            timing.update(observation_id=row['observation_id'],boot_id=row['boot_id'],seq=row['seq'],
                          device_id=row['device_id'],sensor_type=row['sensor_type'],storage_started_monotonic=clock())
        record.update(classification=journal.accept(row), observation=row)
    if timing is not None:
        committed=clock()
        timing.update(commit_returned=True,commit_monotonic=committed,classification=record['classification'],
                      storage_seconds=committed-timing['storage_started_monotonic'],
                      receive_to_commit_seconds=committed-started)
    after_commit()
    if timing is not None:timing['ack_call_monotonic']=clock()
    acknowledge(msg.mid, msg.qos)
    if timing is not None:
        finished=clock()
        timing.update(ack_submitted=True,ack_return_monotonic=finished,
                      commit_to_ack_submit_seconds=finished-timing['commit_monotonic'],
                      receive_to_ack_submit_seconds=finished-started)
    return record
