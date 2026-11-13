"""Causal prefix audit: conservatively group trials sharing a visible history."""
import argparse
from datetime import datetime, timedelta
import math
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from build_b_sim_dataset import verify
from b_feature_audit import validate_split


def fingerprint(rows, end, lateness=0):
    # All history visible at publication; event time never exceeds window end.
    if not math.isfinite(lateness) or lateness<0:raise ValueError("invalid lateness")
    deadline=end+timedelta(seconds=lateness)
    visible = [{k: v for k, v in r.items() if k not in ('observation_id','device_id','boot_id')}
               for r in rows if datetime.fromisoformat(r['received_at']) <= deadline
               and datetime.fromisoformat(r['event_time']) <= end and r['sensor_type'] != 'water']
    visible.sort(key=lambda r: (r['sensor_type'], r['seq']))
    return hashlib.sha256(json.dumps(visible, sort_keys=True, allow_nan=False).encode()).hexdigest()


def audit(source, split_path, output, lateness=2):
    source, output = Path(source), Path(output)
    verification = verify(source)
    split = json.loads(Path(split_path).read_text(encoding='utf-8'))
    trials=json.loads((source/'trials.json').read_text(encoding='utf-8'))['trials']
    partitions=validate_split(split,trials)
    streams = defaultdict(list)
    for line in gzip.decompress((source/'observations.jsonl.gz').read_bytes()).splitlines():
        item = json.loads(line); streams[item['trial_id']].append(item['observation'])
    labels = [json.loads(line) for line in (source/'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    groups = defaultdict(list)
    for label in labels:
        identity = label['trial_id']; end = datetime.fromisoformat(label['window_end'])
        groups[fingerprint(streams[identity], end,lateness=lateness)].append({'trial_id':identity,'window_end':label['window_end'],'split':partitions[identity]})
    duplicates = [items for items in groups.values() if len({r['trial_id'] for r in items}) > 1]
    cross = [items for items in duplicates if len({r['split'] for r in items}) > 1]
    result = {'schema':'b-causal-prefix-audit-v2','parent':verification['dataset_id'],
              'publication_policy':'events <= window_end; arrivals <= window_end + lateness', 'lateness_sec':lateness,
              'water_excluded':True,'duplicate_groups':duplicates,'cross_split_groups':cross,
              'scope':'raw visible prefix equality only; feature-vector/near-duplicate audit pending',
              'training_ready':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
    return {'duplicate_groups':len(duplicates),'cross_split_groups':len(cross),'training_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--split',required=True);p.add_argument('--output',required=True)
    p.add_argument('--lateness',type=float,default=2)
    a=p.parse_args();print(json.dumps(audit(a.source,a.split,a.output,a.lateness)))
