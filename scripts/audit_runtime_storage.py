"""Read-only SQLite/Journal/checkpoint inventory; never authorizes deletion."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3


def quote(name):
    return '"'+name.replace('"','""')+'"'


def references(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('state_checkpoint_ref','asset_refs'):
                for ref in item if isinstance(item,list) else [item]:
                    if isinstance(ref,str) and ref.endswith('.json'):yield ref
            yield from references(item)
    elif isinstance(value,list):
        for item in value:yield from references(item)


def audit(database, checkpoints, journal=None):
    root=checkpoints.resolve()
    files={p.resolve():p.stat().st_size for p in root.glob('*.json') if p.is_file()}
    refs=Counter();counts={};outside=0;unparsed=0
    # One read transaction gives a consistent view of committed DB references.
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=3) as db:
        db.execute('BEGIN')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            counts[table]=db.execute(f'SELECT count(*) FROM {quote(table)}').fetchone()[0]
            columns=[r[1] for r in db.execute(f'PRAGMA table_info({quote(table)})') if 'TEXT' in r[2].upper()]
            for column in columns:
                for (text,) in db.execute(f'SELECT {quote(column)} FROM {quote(table)} WHERE {quote(column)} IS NOT NULL'):
                    if not isinstance(text,str) or not text.lstrip().startswith(('{','[')):continue
                    try:payload=json.loads(text)
                    except ValueError:unparsed+=1;continue
                    for ref in references(payload):
                        path=Path(ref)
                        if not path.is_absolute():outside+=1;continue
                        path=path.resolve()
                        if path.parent!=root:outside+=1;continue
                        refs[path]+=1
        db.rollback()
    result={'scope':'read_only_inventory','table_counts':counts,
            'checkpoint_files':len(files),'checkpoint_bytes':sum(files.values()),
            'referenced_present':len(set(refs)&set(files)),
            'referenced_missing':len(set(refs)-set(files)),
            'no_reference_observed':len(set(files)-set(refs)),
            'no_reference_observed_bytes':sum(size for path,size in files.items() if path not in refs),
            'outside_or_relative_references':outside,'unparsed_json_cells':unparsed,
            'deletion_authorized':False,
            'limitations':['Only explicit asset_refs/state_checkpoint_ref JSON fields in TEXT columns are scanned.',
                          'In-memory, external exports, other databases and historical snapshots are not scanned.',
                          'Filesystem listing and database transaction are not one atomic snapshot; pause writers for retention decisions.',
                          'No observed reference does not mean safe to delete.']}
    if journal is not None:
        with sqlite3.connect(journal.resolve().as_uri()+'?mode=ro',uri=True,timeout=3) as db:
            db.execute('BEGIN')
            names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            result['journal_counts']={name:db.execute(f'SELECT count(*) FROM {quote(name)}').fetchone()[0]
                                      for name in ('observations','attempts','rejected') if name in names}
            db.rollback()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,type=Path)
    parser.add_argument('--checkpoints',required=True,type=Path)
    parser.add_argument('--journal',type=Path)
    args=parser.parse_args()
    if not args.db.is_file() or not args.checkpoints.is_dir() or (args.journal and not args.journal.is_file()):
        parser.error('Existing database, checkpoint directory and optional journal required')
    print(json.dumps(audit(args.db,args.checkpoints,args.journal),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
