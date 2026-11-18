"""Prototype-only simulation context events; checkpoint-backed, no network IO."""
import json
from uuid import uuid4

import b_bridge  # Establish the existing isolated B engine import paths.
from gates import gate
from rules import classify
from store import Store, Conflict, begin_immediate
from edge.contracts.models import _aware


class ContextEvents(Store):
    def __init__(self, path):
        super().__init__(path)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS context_state (device TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def ingest(self, feature, *, now, checkpoint_root, fault_at=None):
        context=gate(feature,_aware(now),checkpoint_root=checkpoint_root)
        window=context['window']
        if window['origin']!='simulation':
            raise ValueError('simulation context only')
        if context['reason']=='WINDOW_STALE':
            raise ValueError('stale context')
        assessment=classify(feature,_aware(now),checkpoint_root=checkpoint_root)
        end=window['window_end']
        with self.connection() as db:
            begin_immediate(db)
            prior=db.execute('SELECT body FROM context_state WHERE device=?',(window['device_id'],)).fetchone()
            if prior:
                state=json.loads(prior[0])
                if _aware(end)<_aware(state['end']):
                    raise Conflict('out-of-order context')
                if end==state['end']:
                    if state['assessment_id']!=assessment['assessment_id']:
                        raise Conflict('conflicting context')
                    return assessment
            row=db.execute("SELECT body FROM events WHERE device_id=? AND event_type='POSSIBLE_UNATTENDED_FLOW' AND lifecycle='OPEN'",(window['device_id'],)).fetchone()
            event=None if row is None else json.loads(row[0])
            if event and event['origin']!='simulation':
                raise Conflict('origin change')
            physical=('ACTIVE' if assessment['situation']=='POSSIBLE_UNATTENDED_FLOW' else
                      'CLEARED' if assessment['situation'] in ('ATTENDED_FLOW','IDLE') else 'UNKNOWN')
            if event is None and physical=='ACTIVE':
                event=dict(schema_version='1.1',event_id=str(uuid4()),device_id=window['device_id'],
                    event_type='POSSIBLE_UNATTENDED_FLOW',lifecycle='OPEN',ack_status='UNACKNOWLEDGED',
                    physical_status=physical,escalation_level='L1',version=1,created_at=now,origin='simulation')
                self._write(db,event,kind='CONTEXT_RISK_DETECTED',now=now,actor='context',refs=[assessment['assessment_id']],fault_at=fault_at)
            elif event and event['physical_status']!=physical:
                event.update(physical_status=physical,version=event['version']+1)
                self._write(db,event,kind='CONTEXT_'+physical,now=now,actor='context',refs=[assessment['assessment_id']],fault_at=fault_at)
            state=dict(end=end,assessment_id=assessment['assessment_id'])
            db.execute('INSERT INTO context_state VALUES(?,?) ON CONFLICT(device) DO UPDATE SET body=excluded.body',
                       (window['device_id'],json.dumps(state)))
        return assessment

    def expire(self, *, now):
        with self.connection() as db:
            begin_immediate(db)
            for row in db.execute('SELECT device,body FROM context_state').fetchall():
                state=json.loads(row['body'])
                if (_aware(now)-_aware(state['end'])).total_seconds()<=10:
                    continue
                event_row=db.execute("SELECT body FROM events WHERE device_id=? AND event_type='POSSIBLE_UNATTENDED_FLOW' AND lifecycle='OPEN'",(row['device'],)).fetchone()
                if event_row:
                    event=json.loads(event_row[0])
                    if event['physical_status']!='UNKNOWN':
                        event.update(physical_status='UNKNOWN',version=event['version']+1)
                        self._write(db,event,kind='CONTEXT_EXPIRED',now=now,actor='timer',refs=[state['assessment_id']])
