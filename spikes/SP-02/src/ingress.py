"""Durability boundary. Storage exceptions propagate without acknowledging."""
from core import normalize
import re


def observation_topic(device_id):
    if not isinstance(device_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device_id):
        raise ValueError('invalid configured device identity')
    return f'prototype/aquaguard/{device_id}/observation'


def process_message(msg, journal, acknowledge, after_commit=lambda: None, *, device_id='prototype01'):
    topic = observation_topic(device_id)
    record = dict(topic=msg.topic, qos=msg.qos, retain=msg.retain, raw_hex=msg.payload.hex())
    try:
        if msg.topic != topic:
            raise ValueError('unexpected topic')
        if msg.retain:
            raise ValueError('retained observation rejected')
        row = normalize(msg.payload, device_id, 'simulation')
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        record.update(classification='invalid', error=str(exc))
        journal.reject(record)
    else:
        record.update(classification=journal.accept(row), observation=row)
    after_commit()
    acknowledge(msg.mid, msg.qos)
    return record
