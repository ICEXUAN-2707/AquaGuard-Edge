"""Read-only phase evidence and local assertions; never overall acceptance."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def capture(business,journal):
    with closing(sqlite3.connect(Path(business).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        db.execute('BEGIN')
        events=[json.loads(row[0]) for row in db.execute("SELECT body FROM events WHERE device_id='demo01' AND event_type='WATER_CONTACT' AND lifecycle='OPEN'")]
        transitions=db.execute("SELECT count(*) FROM transitions t JOIN events e ON e.event_id=t.event_id WHERE e.device_id='demo01' AND e.event_type='WATER_CONTACT'").fetchone()[0]
        state=db.execute('SELECT boot,cursor FROM mqtt_consumer WHERE singleton=1').fetchone()
        quarantine=db.execute('SELECT count(*) FROM mqtt_quarantine').fetchone()[0]
        db.rollback()
    with closing(sqlite3.connect(Path(journal).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        duplicates=db.execute("SELECT count(*) FROM attempts WHERE classification='duplicate'").fetchone()[0]
    return dict(water_events=events,water_transitions=transitions,boot=state[0] if state else None,
                cursor=state[1] if state else 0,quarantine=quarantine,duplicates=duplicates,
                note='Business transaction and Journal count are separate observational snapshots.')


def evaluate(stage,before,after,samples):
    checks=[]
    def check(name,value):checks.append({'name':name,'satisfied':bool(value)})
    try:
        name=stage['name'];events=after['water_events']
        check('one_open_water_event',len(events)==1)
        if len(events)!=1:return dict(status='VIOLATED',checks=checks)
        event=events[0]
        check('simulation_origin',event['origin']=='simulation')
        if name!='shutdown':check('expected_consumer_boot',after['boot']==stage['boot'])
        if name=='publisher_stop':
            check('water_unknown_after_ttl',event['physical_status']=='UNKNOWN')
            check('same_event_after_expiry',event['event_id']==before['water_events'][0]['event_id'])
        elif name!='shutdown':check('water_active',event['physical_status']=='ACTIVE')
        if name=='continuous':
            check('normal_samples_present',len(samples)>0)
            check('normal_live_available',bool(samples) and all(row.get('live',{}).get('status')==200 for row in samples))
        if name in ('resume_duplicate','edge_restart','new_boot'):
            previous=before['water_events'][0]
            check('event_identity_preserved',event['event_id']==previous['event_id'])
            check('ack_state_preserved',event['ack_status']==previous['ack_status'])
            check('cursor_non_decreasing',after['cursor']>=before['cursor'])
        if name=='resume_duplicate':
            check('duplicates_observed',after['duplicates']-before['duplicates']>=3)
            check('only_expected_restore_transition',after['water_transitions']-before['water_transitions']==1)
        if name=='new_boot':check('retired_boot_batch_quarantined',after['quarantine']-before['quarantine']>=3)
        return dict(status='SATISFIED' if all(row['satisfied'] for row in checks) else 'VIOLATED',checks=checks)
    except (KeyError,IndexError,TypeError,AttributeError):
        return dict(status='INCOMPLETE',checks=checks,reason='required phase evidence missing')
