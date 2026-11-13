"""Exhaustive cross-partition feature proximity audit, descriptive only."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

# Fixed engineering scales, not fitted from held-out data.
SCALES={'flow_mean_lpm':1.0,'flow_max_lpm':1.0,'flow_active_ratio':1.0,
        'flow_streak_sec':30.0,'flow_change_count':1.0,'presence_occupied_ratio':1.0,
        'presence_transition_count':1.0,'absence_after_flow_sec':30.0,'data_coverage_ratio':1.0}

def distance(a,b):
    if set(a)!=set(SCALES) or set(b)!=set(SCALES):raise ValueError('unexpected feature set')
    if any(a[k] is None or b[k] is None for k in SCALES):return None
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for row in (a,b) for v in row.values()):
        raise ValueError('non-finite vector')
    return max(abs(a[k]-b[k])/scale for k,scale in SCALES.items())

def audit(directory):
    directory=Path(directory)
    data=(directory/'features.jsonl').read_bytes()
    manifest=json.loads((directory/'manifest.json').read_text())
    if hashlib.sha256(data).hexdigest()!=manifest['features_sha256']:raise ValueError('feature digest mismatch')
    rows=[json.loads(line) for line in data.splitlines()]
    pairs=[];compared=0;incomplete=0
    for a,b in itertools.combinations(rows,2):
        if a['split']==b['split']:continue
        d=distance(a['features'],b['features'])
        if d is None:incomplete+=1;continue
        compared+=1
        if d<=0.05:
            pairs.append(dict(left=[a['trial_id'],a['window_end']],right=[b['trial_id'],b['window_end']],
                              distance=d,kind='exact' if d==0 else 'near',
                              eligible=not a['rejection_reasons'] and not b['rejection_reasons']))
    return dict(schema='b-proximity-audit-v1',features_sha256=manifest['features_sha256'],scales=SCALES,
                metric='max absolute scaled coordinate difference',threshold=0.05,
                compared_pairs=compared,incomplete_pairs_excluded=incomplete,pairs=pairs,
                limitation='descriptive feature-space similarity, not proof of raw-source independence; no automatic split edits',
                training_ready=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--features',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=audit(a.features)
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'compared_pairs':result['compared_pairs'],'exact_pairs':sum(r['kind']=='exact' for r in result['pairs']),'near_pairs':sum(r['kind']=='near' for r in result['pairs'])}))
