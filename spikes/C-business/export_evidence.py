"""Export a completed local verifier run without environment files or tools."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED


def export(directory, output):
    directory=Path(directory).resolve()
    cleanup=json.loads((directory/'cleanup.json').read_text())
    if not cleanup or not all(row.get('exit_confirmed') is True for row in cleanup):
        raise ValueError('completed owned-process cleanup required before export')
    names=['run.json','result.json','cleanup.json','recovery.json','events.json','manifest.jsonl',
           'second-boot/manifest.jsonl','browser/result.json']
    names += [str(p.relative_to(directory)).replace('\\','/') for p in (directory/'browser').glob('*.png')]
    checksums={}
    with tempfile.TemporaryDirectory() as temp:
        databases=[]
        for name in ('business.sqlite','journal.sqlite'):
            source=directory/name
            if source.is_file():
                target=Path(temp)/name
                with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as original:
                    with closing(sqlite3.connect(target)) as snapshot:
                        original.backup(snapshot)
                        if snapshot.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                            raise ValueError('database snapshot integrity failure')
                databases.append((name,target))
        checkpoints=directory/'business.sqlite.checkpoints'
        assets=[(str(p.relative_to(directory)).replace('\\','/'),p) for p in checkpoints.glob('*.json')]
        assets += [(name,directory/name) for name in names if (directory/name).is_file()]
        assets += databases
        # Exclusive creation preserves an earlier evidence package.
        with ZipFile(output,'x',compression=ZIP_DEFLATED) as archive:
            for name,source in assets:
                data=source.read_bytes()
                archive.writestr(name,data)
                checksums[name]=hashlib.sha256(data).hexdigest()
            archive.writestr('EXPORT_MANIFEST.json',json.dumps(dict(
                format='aquaguard-local-evidence-v1',files=checksums,
                limitation='Completed local run; per-database backups, not a cross-database live snapshot. Checkpoint references preserve original paths; replay requires relocation mapping.',
                excluded=['environment files','credentials','tools','raw service logs']),indent=2))
    return len(checksums)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(dict(files=export(args.directory,args.output),output=str(args.output))))
