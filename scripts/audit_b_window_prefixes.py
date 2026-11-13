"""Causal prefix audit: conservatively group trials sharing a visible history."""
import argparse
from datetime import datetime
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from build_b_sim_dataset import verify


def fingerprint(rows, end):
    # All history, including pre-window state; strictly no future arrivals/events.
    visible = [{k: v for k, v in r.items() if k not in ('observation_id','device_id','boot_id')}
               for r in rows if datetime.fromisoformat(r['received_at']) <= end
               and datetime.fromisoformat(r['event_time']) <= end and r['sensor_type'] != 'water']
    visible.sort(key=lambda r: (r['sensor_type'], r['seq']))
    return hashlib.sha256(json.dumps(visible, sort_keys=True, allow_nan=False).encode()).hexdigest()


def audit(source, split_path, output):
    source, output = Path(source), Path(output)
    verification = verify(source)
    split = json.loads(Path(split_path).read_text(encoding='utf-8'))
    partitions = {i:s for s, ids in split['trials'].items() for i in ids}
    streams = defaultdict(list)
    for line in gzip.decompress((source/'observations.jsonl.gz').read_bytes()).splitlines():
        item = json.loads(line); streams[item['trial_id']].append(item['observation'])
    labels = [json.loads(line) for line in (source/'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    groups = defaultdict(list)
    for label in labels:
        identity = label['trial_id']; end = datetime.fromisoformat(label['window_end'])
        groups[fingerprint(streams[identity], end)].append({'trial_id':identity,'window_end':label['window_end'],'split':partitions[identity]})
    duplicates = [items for items in groups.values() if len({r['trial_id'] for r in items}) > 1]
    cross = [items for items in duplicates if len({r['split'] for r in items}) > 1]
    result = {'schema':'b-causal-prefix-audit-v1','parent':verification['dataset_id'],
              'publication_policy':'window_end, zero waiting; event_time and received_at <= end',
              'water_excluded':True,'duplicate_groups':duplicates,'cross_split_groups':cross,
              'scope':'raw visible prefix equality only; feature-vector/near-duplicate audit pending',
              'training_ready':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
    return {'duplicate_groups':len(duplicates),'cross_split_groups':len(cross),'training_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--split',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(audit(a.source,a.split,a.output)))
