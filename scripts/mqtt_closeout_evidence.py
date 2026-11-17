"""Offline runtime lock, read-only checkpoint inventory and joined latency evidence."""
import argparse
from contextlib import closing
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import sqlite3
import sys


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def runtime_lock(root,broker,broker_version):
    root=Path(root)
    if not isinstance(broker_version,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',broker_version):raise ValueError('explicit numeric broker version required')
    files={name:digest(root/name) for name in ('requirements-app.lock.txt','web/package-lock.json')}
    canonical=lambda name:re.sub(r'[-_.]+','-',name).lower()
    installed={canonical(dist.metadata['Name']):dist.version for dist in importlib.metadata.distributions()}
    for line in (root/'requirements-app.lock.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        name,separator,version=line.partition('==')
        if not separator or installed.get(canonical(name))!=version.strip():raise ValueError('installed dependency differs from application lock: '+name)
    return dict(schema_version=1,python=platform.python_version(),implementation=platform.python_implementation(),
                platform=sys.platform,machine=platform.machine(),lock_files=files,installed=installed,
                broker_sha256=digest(broker),broker_version=broker_version)


def checkpoint_sizes(folder):
    folder=Path(folder).resolve()
    files=[path for path in folder.glob('*.json') if path.is_file() and path.resolve().parent==folder]
    return dict(directory_exists=folder.is_dir(),files=len(files),bytes=sum(path.stat().st_size for path in files))


def checkpoint_inventory(database,folder):
    folder=Path(folder).resolve();sizes=checkpoint_sizes(folder);refs=set();outside=0;unparsed=0
    def visit(value):
        nonlocal outside
        if isinstance(value,dict):
            ref=value.get('state_checkpoint_ref')
            if isinstance(ref,str):
                path=Path(ref)
                if not path.is_absolute() or path.resolve().parent!=folder:outside+=1
                else:refs.add(path.resolve())
            for key,item in value.items():
                if key=='asset_refs' and isinstance(item,list):
                    for ref in item:
                        if isinstance(ref,str) and Path(ref).is_absolute() and Path(ref).resolve().parent==folder:refs.add(Path(ref).resolve())
                visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        db.execute('BEGIN')
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            quote=lambda name:'"'+name.replace('"','""')+'"'
            for row in db.execute('PRAGMA table_info('+quote(table)+')').fetchall():
                if 'TEXT' not in row[2].upper():continue
                for (value,) in db.execute('SELECT '+quote(row[1])+' FROM '+quote(table)):
                    if not isinstance(value,str) or not value.lstrip().startswith(('{','[')):continue
                    try:visit(json.loads(value))
                    except ValueError:unparsed+=1
        db.rollback()
    missing=sum(not path.is_file() for path in refs)
    return dict(**sizes,referenced_checkpoints=len(refs),missing_referenced=missing,outside_checkpoint_refs=outside,
                unreferenced_observed=max(0,sizes['files']-(len(refs)-missing)),deletion_authorized=False,
                unparsed_json_cells=unparsed,ok=sizes['directory_exists'] and bool(refs) and missing==0 and outside==0 and unparsed==0,
                note='Read-only explicit references; filesystem/DB are non-atomic. No observed reference never authorizes deletion. New owned run starts with zero files; final count/bytes are its observed growth.')


def consumption_latency(publisher_files,consumer_file):
    result=dict(scope='same_host_publish_start_to_consumer_cursor_commit',publications=0,consumptions=0,valid_publications=0,invalid=0,
                failed_publications=0,matched_unique=0,acceptance_passed=False)
    emitted={};consumed={}
    try:
        if not publisher_files:raise FileNotFoundError('publisher evidence missing')
        for paths,kind in ((publisher_files,'publisher'),([consumer_file],'consumer')):
            for path in paths:
                with Path(path).open(encoding='utf-8') as stream:
                    for line in stream:
                        if result['publications']+result['consumptions']>=1000000:raise ValueError('evidence bound exceeded')
                        key='publications' if kind=='publisher' else 'consumptions';result[key]+=1
                        try:
                            row=json.loads(line);identity=row['observation_id']
                            if row.get('scope')!=('publish_attempt' if kind=='publisher' else 'consumer_cursor_commit'):raise ValueError('wrong clock evidence scope')
                            if not isinstance(identity,str) or not identity:raise ValueError('identity required')
                            field='publish_start' if kind=='publisher' else 'cursor_commit'
                            value=row[field]
                            if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('invalid monotonic timestamp')
                            if kind=='publisher' and row.get('puback_returned') is not True:
                                result['failed_publications']+=1;continue
                            if kind=='publisher':result['valid_publications']+=1
                            target=emitted if kind=='publisher' else consumed
                            target[identity]=min(target.get(identity,value),value)
                        except (KeyError,TypeError,ValueError):result['invalid']+=1
    except (OSError,UnicodeError,ValueError) as exc:
        result.update(status='INCOMPLETE',error_type=type(exc).__name__);return result
    values=[]
    for identity in emitted.keys()&consumed.keys():
        value=consumed[identity]-emitted[identity]
        if value<0:result['invalid']+=1
        else:values.append(value)
    values.sort();result['matched_unique']=len(values)
    result.update(unmatched_publications=len(emitted.keys()-consumed.keys()),unmatched_consumptions=len(consumed.keys()-emitted.keys()),
                  duplicate_publications=max(0,result['valid_publications']-len(emitted)),
                  p50_seconds=values[math.ceil(len(values)*.5)-1] if values else None,
                  p95_seconds=values[math.ceil(len(values)*.95)-1] if values else None,max_seconds=max(values) if values else None,
                  note='Same Windows host perf_counter domain, includes instrumentation. Unique IDs use first successful emission/commit; duplicate publications remain counted. Cursor commit is not event/window/UI/cloud completion; quarantine also commits a cursor.')
    result['status']='AVAILABLE' if values and not any(result[key] for key in ('invalid','failed_publications','unmatched_publications','unmatched_consumptions')) else 'INCOMPLETE'
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Prepare a runtime lock without executing the broker or connecting to a service')
    parser.add_argument('--broker',required=True,type=Path);parser.add_argument('--broker-version',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    value=runtime_lock(Path(__file__).resolve().parents[1],args.broker,args.broker_version)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
