"""Durability boundary. Storage exceptions propagate without acknowledging."""
from core import normalize


def process_message(msg, journal, acknowledge, after_commit=lambda: None):
    record = dict(topic=msg.topic, qos=msg.qos, retain=msg.retain, raw_hex=msg.payload.hex())
    try:
        if msg.topic != 'prototype/aquaguard/prototype01/observation':
            raise ValueError('unexpected topic')
        if msg.retain:
            raise ValueError('retained observation rejected')
        row = normalize(msg.payload, 'prototype01', 'simulation')
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        record.update(classification='invalid', error=str(exc))
        journal.reject(record)
    else:
        record.update(classification=journal.accept(row), observation=row)
    after_commit()
    acknowledge(msg.mid, msg.qos)
    return record
