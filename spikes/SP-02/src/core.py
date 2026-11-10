"""prototype_only: deterministic ingress and durable identity classification."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from edge.contracts.models import validate_raw_observation


def identity(row):
    return [row[k] for k in ('device_id', 'sensor_type', 'boot_id', 'seq')]


def observation_id(row):
    encoded = json.dumps(identity(row), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def normalize(payload, device_id, source, received_at=None):
    row = json.loads(payload)
    if not isinstance(row, dict):
        raise ValueError('payload must be an object')
    if 'received_at' in row:
        raise ValueError('wire payload cannot supply received_at')
    if row.get('device_id') != device_id or row.get('source') != source:
        raise ValueError('device/source differs from trusted configuration')
    if row.get('time_basis') != 'RECEIVED_FALLBACK' or row.get('event_time') is not None:
        raise ValueError('only untrusted device time supported in this prototype')
    if row.get('observation_id') != observation_id(row):
        raise ValueError('observation identity mismatch')
    row['received_at'] = received_at or datetime.now(timezone.utc).isoformat()
    return validate_raw_observation(row).model_dump(mode='json')


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, key TEXT UNIQUE, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (number INTEGER PRIMARY KEY, classification TEXT, body TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS rejected (number INTEGER PRIMARY KEY, body TEXT NOT NULL)')
        self.db.commit()

    def accept(self, row):
        key = json.dumps(identity(row), separators=(',', ':'))
        content = {k: v for k, v in row.items() if k != 'received_at'}
        body = json.dumps(content, sort_keys=True, separators=(',', ':'))
        with self.db:
            old = self.db.execute('SELECT body FROM observations WHERE key=? OR id=?', (key, row['observation_id'])).fetchall()
            if old:
                result = 'duplicate' if len(old) == 1 and old[0][0] == body else 'conflict'
            else:
                previous = [json.loads(r[0]) for r in self.db.execute('SELECT body FROM observations')]
                scope = identity(row)[:3]
                result = 'out_of_order' if any(identity(r)[:3] == scope and r['seq'] > row['seq'] for r in previous) else 'new'
                self.db.execute('INSERT INTO observations VALUES (?,?,?)', (row['observation_id'], key, body))
            self.db.execute('INSERT INTO attempts(classification,body) VALUES (?,?)', (result, json.dumps(row)))
        return result

    def export(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM attempts WHERE classification IN ('new','out_of_order') ORDER BY number")]

    def reject(self, record):
        with self.db:
            self.db.execute('INSERT INTO rejected(body) VALUES (?)', (json.dumps(record),))

    def close(self):
        self.db.close()


def sample(seq=0, sensor='water', boot='boot-1', device_id='prototype01'):
    values = {'water': {'wet': False}, 'presence': {'present': True, 'moving': False, 'still': True},
              'flow': {'pulse_count': 2, 'interval_ms': 1000, 'estimated_lpm': 0.2, 'calibration_id': 'simulation-only'}}
    row = dict(schema_version='1.1', device_id=device_id, sensor_type=sensor, boot_id=boot,
               seq=seq, uptime_ms=seq * 1000, event_time=None, time_basis='RECEIVED_FALLBACK',
               value=values[sensor], quality='valid', source='simulation')
    row['observation_id'] = observation_id(row)
    return row
