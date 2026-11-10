"""Local prototype close operation; shared A/B contracts are unchanged."""
import json

from pydantic import Field
from typing import Literal
from edge.contracts.models import DTO, _aware
from store import Conflict, NotFound, VersionConflict, IdempotencyConflict, canonical


class CloseRequest(DTO):
    schema_version: Literal['1.1']
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


def close_event(store, event_id, payload, *, now, authorized=False):
    if authorized is not True:
        raise PermissionError('close requires backend authorization')
    request = CloseRequest.model_validate(payload).model_dump(mode='json')
    operation = dict(operation='CLOSE', **request)
    clock = _aware(now)
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT request,response FROM operations WHERE event_id=? AND key=?',
                           (event_id, request['idempotency_key'])).fetchone()
        if prior:
            if prior[0] != canonical(operation):
                raise IdempotencyConflict('operation key reused')
            return json.loads(prior[1])
        row = db.execute('SELECT body FROM events WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise NotFound(event_id)
        event = json.loads(row[0])
        if event['version'] != request['expected_version']:
            raise VersionConflict(request['expected_version'], event['version'])
        if (event['lifecycle'] != 'OPEN' or event['ack_status'] != 'ACKNOWLEDGED'
                or event['physical_status'] != 'CLEARED'):
            raise Conflict('close requires acknowledged, cleared OPEN event')
        if event['event_type'] == 'WATER_CONTACT':
            state = db.execute('SELECT body FROM water_state WHERE device_id=?', (event['device_id'],)).fetchone()
            if state is None:
                raise Conflict('missing recovery evidence')
            state = json.loads(state[0])
            age = (clock - _aware(state['observed_at'])).total_seconds()
            if age < 0 or age > json.loads(state['config'])['ttl']:
                raise Conflict('recovery evidence expired')
            refs = [state['observation_id']]
        elif event['event_type'] == 'POSSIBLE_UNATTENDED_FLOW':
            state = db.execute('SELECT body FROM context_state WHERE device=?', (event['device_id'],)).fetchone()
            if state is None:
                raise Conflict('missing recovery evidence')
            state = json.loads(state[0])
            age = (clock - _aware(state['end'])).total_seconds()
            if age < 0 or age > 10:
                raise Conflict('recovery evidence expired')
            refs = [state['assessment_id']]
        else:
            raise Conflict('unsupported event type')
        event.update(lifecycle='CLOSED', version=event['version'] + 1)
        response = store._write(db, event, kind='CLOSED', now=now, actor='user', refs=refs)
        db.execute('INSERT INTO operations VALUES(?,?,?,?)',
                   (event_id, request['idempotency_key'], canonical(operation), canonical(response)))
        return response
