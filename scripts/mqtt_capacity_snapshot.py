"""Read-only MQTT Journal/consumer snapshot; starts no processes or traffic."""
import argparse
import json
from pathlib import Path
import sqlite3
from contextlib import closing


def file_inventory(path):
    """Non-atomic file observations; absent sidecars are zero, errors propagate."""
    result={}
    for name,suffix in (('main',''),('wal','-wal'),('shm','-shm')):
        try:result[name]=Path(str(path)+suffix).stat().st_size
        except FileNotFoundError:
            if not suffix:raise
            result[name]=0
    return result

def snapshot(journal,business):
    journal,business=Path(journal).resolve(),Path(business).resolve()
    with closing(sqlite3.connect(business.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        row=db.execute('SELECT journal,cursor FROM mqtt_consumer WHERE singleton=1').fetchone()
    if row is None:raise ValueError('consumer not initialized')
    if Path(row[0]).resolve()!=journal:raise ValueError('consumer journal binding mismatch')
    with closing(sqlite3.connect(journal.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        db.execute('BEGIN')
        counts={name:db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('observations','attempts','rejected')}
        pending=db.execute("SELECT count(*) FROM attempts WHERE number>? AND classification IN ('new','out_of_order')",(row[1],)).fetchone()[0]
        latest=db.execute('SELECT max(number) FROM attempts').fetchone()[0]
        db.rollback()
    if type(row[1]) is not int or row[1]<0 or row[1]>(latest or 0):
        raise ValueError('consumer cursor outside journal inventory; possible replacement or truncation')
    files={'journal':file_inventory(journal),'business':file_inventory(business)}
    return {'scope':'read_only_mqtt_capacity','counts':counts,'consumer_cursor':row[1],
            'journal_latest_attempt':latest,'pending_eligible_attempts':pending,
            'journal_bytes':files['journal']['main'],'business_bytes':files['business']['main'],
            'file_bytes':files,
            'note':'Separate databases and file sizes are not atomic snapshots; backlog is observational. Legacy byte fields are main files only; file_bytes includes WAL/SHM. No performance or long-duration acceptance.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal',required=True,type=Path);parser.add_argument('--db',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(snapshot(args.journal,args.db),indent=2))
