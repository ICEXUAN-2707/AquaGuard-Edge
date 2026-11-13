"""Extract approved M3/M4 features; no training and no derived truth labels."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'spikes/SP-04'))
from experiment.config import MODEL_FEATURE_NAMES
from alignment import align, ALGORITHM_VERSION
from engine import compute
from experiment.ml import feature_vector
from build_b_sim_dataset import verify
from b_feature_audit import validate_split, provenance, diagnostics
CONFIG=dict(width=30,lateness=2,ttl=10,flow_threshold=0.1)

def extract(source,split_path,output):
    source,output=Path(source),Path(output)
    verified=verify(source)
    split=json.loads(Path(split_path).read_text(encoding='utf-8'))
    trials=json.loads((source/'trials.json').read_text(encoding='utf-8'))['trials']
    partitions=validate_split(split,trials)
    streams=defaultdict(list)
    for line in gzip.decompress((source/'observations.jsonl.gz').read_bytes()).splitlines():
        item=json.loads(line);streams[item['trial_id']].append(item['observation'])
    labels=[json.loads(line) for line in (source/'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    records=[];groups=defaultdict(list)
    for label in labels:
        identity=label['trial_id'];end=datetime.fromisoformat(label['window_end']); deadline=end+timedelta(seconds=CONFIG['lateness'])
        history=[r for r in streams[identity] if datetime.fromisoformat(r['received_at'])<=deadline and datetime.fromisoformat(r['event_time'])<=end]
        window=align(history,[end],**CONFIG)['windows'][0]
        result=compute(window,history,alignment_config=CONFIG)
        vector=feature_vector(result['features'])
        coverage={s:window['sensor_summary'][s]['coverage_ratio'] for s in ('flow','presence')}
        reasons=[]
        if vector is None:reasons.append('INCOMPLETE_FEATURE_VECTOR')
        for sensor in coverage:
            if coverage[sensor]<0.8:reasons.append(sensor.upper()+'_LOW_COVERAGE')
            if window['sensor_summary'][sensor]['state']=='unknown':reasons.append(sensor.upper()+'_STATE_UNKNOWN')
        history_digest=hashlib.sha256(json.dumps(history,sort_keys=True,allow_nan=False).encode()).hexdigest()
        record=dict(input_history_sha256=history_digest, input_observation_count=len(history), trial_id=identity,window_end=label['window_end'],split=partitions[identity],
                    features={n:result['features'].get(n) for n in MODEL_FEATURE_NAMES},coverage=coverage,
                    rejection_reasons=reasons, quality_rejection_reasons=[r for r in reasons if r != 'INCOMPLETE_FEATURE_VECTOR'], model_vector_complete=vector is not None, published_at=deadline.isoformat(), feature_version=result['feature_version'],
                    original_episode_target=label['candidate_target'],candidate_target=None)
        records.append(record)
        digest=hashlib.sha256(json.dumps(record['features'],sort_keys=True,allow_nan=False).encode()).hexdigest()
        groups[digest].append(dict(trial_id=identity,window_end=label['window_end'],split=partitions[identity]))
    cross=[items for items in groups.values() if len({r['split'] for r in items})>1]
    output.mkdir(parents=True,exist_ok=False)
    data=''.join(json.dumps(r,sort_keys=True,allow_nan=False)+'\n' for r in records).encode()
    (output/'features.jsonl').write_bytes(data)
    manifest=dict(schema='b-expanded-features-v2',parent=verified,alignment=ALGORITHM_VERSION,config=CONFIG,
                  feature_names=list(MODEL_FEATURE_NAMES),windows=len(records),rejected=sum(bool(r['rejection_reasons']) for r in records),
                  cross_split_feature_groups=cross,features_sha256=hashlib.sha256(data).hexdigest(),
                  publication_policy='window_end + 2 seconds; no events after window_end', quality_rejected=sum(bool(r['quality_rejection_reasons']) for r in records), incomplete_vectors=sum(not r['model_vector_complete'] for r in records), training_ready=False,label_status='candidate labels not assigned; original episode truth retained',
                  code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  split_sha256=hashlib.sha256(Path(split_path).read_bytes()).hexdigest())
    manifest['provenance']=provenance(ROOT,source,Path(split_path))
    manifest['diagnostics']=diagnostics(records,trials)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return {k:manifest[k] for k in ('windows','rejected','training_ready')}|{'cross_split_feature_groups':len(cross)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--split',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(extract(a.source,a.split,a.output)))
