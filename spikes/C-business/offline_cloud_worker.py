"""Explicit IoTDA mapping/worker assembly with a network-free failure transport."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import sqlite3
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.base import RetryableFailure, PermanentFailure
from adapters.iotda import IoTDAAdapter
from cloud_config import load_config, ConfigError
from delivery import DeliveryService
from outbox import Worker
from store import canonical


def validate_business_database(path):
    path=Path(path).resolve()
    required={
        'events':{'event_id','device_id','event_type','lifecycle','body'},
        'transitions':{'transition_id','event_id','version','body'},
        'outbox':{'transition_id','message_id','body'},
        'operations':{'event_id','key','request','response'},
        'outbox_payloads':{'transition_id','body'},
        'delivery_attempts':{'token','message_id','number','claimed_at','lease_until','result'},
        'delivery_policy':{'singleton','body'},
    }
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            db.execute('BEGIN')
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(required)<=tables:raise ValueError('existing initialized business worker database required')
            for table,columns in required.items():
                actual={row[1] for row in db.execute('PRAGMA table_info('+table+')')}
                if not columns<=actual:raise ValueError('incompatible business database structure')
            indexes={row[1]:row for row in db.execute('PRAGMA index_list(events)')}
            index=indexes.get('unique_open')
            index_sql=db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='unique_open'").fetchone()
            index_columns=[row[2] for row in db.execute('PRAGMA index_info(unique_open)')]
            sql='' if not index_sql or index_sql[0] is None else ''.join(index_sql[0].upper().split()).replace('IFNOTEXISTS','').rstrip(';')
            expected_index="CREATEUNIQUEINDEXUNIQUE_OPENONEVENTS(DEVICE_ID,EVENT_TYPE)WHERELIFECYCLE='OPEN'"
            if not index or not index[2] or not index[4] or index_columns!=['device_id','event_type'] or sql!=expected_index:
                raise ValueError('required unique OPEN index missing or incompatible')
            rows=db.execute('SELECT singleton,body FROM delivery_policy').fetchall()
            expected=canonical(dict(version='mock-r05-v1',base=1,cap=60,lease=10,maximum=5))
            if rows!=[(1,expected)]:raise ValueError('worker policy changed or missing; reviewed initialization/migration required')
            db.rollback()
    except sqlite3.Error:
        raise ValueError('existing initialized business worker database required') from None
    return path


class OfflineTransport:
    def __init__(self,mode='retry'):
        if mode not in ('retry','permanent'):raise ValueError('offline failure mode required')
        self.mode=mode;self.closed=False;self.calls=0
    def send(self,payload,*,message_id,attempt_token):
        if self.closed:raise RuntimeError('offline transport closed')
        self.calls+=1
        # No socket/client construction and no fabricated cloud acceptance.
        return RetryableFailure('OFFLINE_NO_NETWORK') if self.mode=='retry' else PermanentFailure('OFFLINE_REJECTED')
    def close(self):self.closed=True


def utcnow():return datetime.now(timezone.utc).isoformat()


def assemble(path,config,*,mode='retry',clock=utcnow):
    if not Path(path).is_file():raise ValueError('existing isolated business database required')
    if not config.bindings or any(b.authorization_class!='simulation_test' or b.allowed_origins!=('simulation',) for b in config.bindings):
        raise ConfigError('offline worker requires simulation-only test bindings')
    if mode not in ('retry','permanent') or not callable(clock):raise ValueError('valid offline mode and clock required')
    path=validate_business_database(path)
    transport=OfflineTransport(mode)
    try:return DeliveryService(Worker(path),IoTDAAdapter(config,transport),finish_clock=clock)
    except BaseException:
        transport.close()
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--mode',choices=('retry','permanent'),default='retry')
    parser.add_argument('--steps',type=int,default=1)
    args=parser.parse_args()
    if not 1<=args.steps<=100:parser.error('steps must be 1..100')
    service=assemble(args.db,load_config(),mode=args.mode)
    try:
        statuses=[service.step(now=utcnow()) for _ in range(args.steps)]
        print(json.dumps({'scope':'offline_mapping_worker','network_enabled':False,'cloud_accepted':False,'statuses':statuses}))
    finally:service.close()


if __name__=='__main__':main()
