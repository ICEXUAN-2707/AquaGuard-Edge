"""Consume SP-02's committed simulation journal, not broker callbacks.

One demo01 boot per business database. Hardware authorization is not enabled.
The bounded batch and original timestamps keep backlog from becoming fresh data.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from online import Simulation
from policy import Policy
from edge.contracts.models import validate_raw_observation, _aware


class JournalRuntime(Simulation):
    def __init__(self, path, checkpoints, start, journal):
        self.journal = Path(journal).resolve()
        if not self.journal.is_file() or self.journal == Path(path).resolve():
            raise ValueError('separate existing MQTT journal required')
        super().__init__(path, checkpoints, start, trial='mqtt-trial', initialize_trial=False)
        with self.water.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS mqtt_consumer (singleton INTEGER PRIMARY KEY CHECK(singleton=1), journal TEXT, boot TEXT, cursor INTEGER)')
            state = db.execute('SELECT journal,boot,cursor FROM mqtt_consumer WHERE singleton=1').fetchone()
        if state and state[0] != str(self.journal):
            raise ValueError('consumer database belongs to another journal')
        self.input_boot = state[1] if state else None
        self.cursor = state[2] if state else 0
        # Reload bounded history on restart; do not re-ingest old water evidence.
        with self.connection() as db:
            records = db.execute("SELECT body FROM attempts WHERE number<=? AND classification IN ('new','out_of_order') ORDER BY number DESC LIMIT 2048", (self.cursor,)).fetchall()
        self.rows = [json.loads(r[0]) for r in reversed(records)]
        if self.rows:
            self.start = _aware(self.rows[0]['received_at'])
            self.next_end = self.start + timedelta(seconds=30)
        with self.water.connection() as db:
            prior=db.execute('SELECT body FROM context_state WHERE device=?',('demo01',)).fetchone()
        if prior:
            self.next_end=_aware(json.loads(prior[0])['end'])+timedelta(seconds=5)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.journal.as_uri()+'?mode=ro', uri=True)
        try:
            yield db
        finally:
            db.close()

    def step(self, now):
        if now.tzinfo is None or now < self.last:
            raise ValueError('aware monotonic clock required')
        self.last = now
        with self.connection() as db:
            records = db.execute("SELECT number,body FROM attempts WHERE number>? AND classification IN ('new','out_of_order') ORDER BY number LIMIT 512",(self.cursor,)).fetchall()
        for number, body in records:
            row = json.loads(body)
            validate_raw_observation(row)
            if row['device_id'] != 'demo01' or row['source'] != 'simulation':
                raise ValueError('MQTT runtime permits demo01 simulation only')
            boot = row['boot_id']
            if self.input_boot is not None and boot != self.input_boot:
                raise ValueError('new MQTT boot requires a fresh trial database')
            age = (now-_aware(row['received_at'])).total_seconds()
            if age < 0:
                # A callback may commit after this scheduler tick sampled now.
                # Defer it to the next tick without consuming or relabeling it.
                break
            if row['sensor_type'] == 'water' and age < 10:
                # Stable observation IDs make crash-before-cursor replay idempotent.
                self.water.ingest(row,now=row['received_at'],policy=Policy(10,2),
                    policy_version='g1-simulation-v1',trusted_device='demo01',
                    trusted_source='simulation',escalation_level='L2')
            with self.water.connection() as db:
                db.execute('INSERT INTO mqtt_consumer VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET boot=excluded.boot,cursor=excluded.cursor',
                           (str(self.journal),boot,number))
            self.input_boot, self.cursor = boot, number
            if not self.rows:
                self.start = _aware(row['received_at'])
                self.next_end = self.start+timedelta(seconds=30)
            self.rows.append(row)
        return self.publish(now)
