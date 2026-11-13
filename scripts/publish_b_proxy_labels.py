"""Publish an explicit causal evidence-proxy label contract, never efficacy truth."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CONTRACT={'version':'b-candidate-proxy-label-v1','target':'observable evidence candidate, not true unoccupied water use',
          'publication':'window_end+2 seconds; events <= window_end','positive':'active flow ratio > 0 and absence_after_flow_sec >= 10',
          'negative':'eligible evidence not meeting positive definition','unknown':'any P1 quality rejection or incomplete nine-feature vector',
          'annotation_basis':'deterministic feature-derived engineering proxy; no independent human annotation',
          'limitations':['rule-derived target may favor C2; cannot establish ML efficacy or superiority',
                         'hidden-present and unattended may both be candidate-positive despite different true occupancy',
                         'future return never revises an earlier window label','development holdout has been exposed']}

def label(row):
    if row['rejection_reasons']:return None,'QUALITY_OR_FEATURES_INSUFFICIENT'
    f=row['features']
    if f['flow_active_ratio']>0 and f['absence_after_flow_sec']>=10:return True,'FLOW_AND_OBSERVED_ABSENCE_DURATION'
    return False,'CANDIDATE_EVIDENCE_NOT_MET'

def publish(features,output):
    features,output=Path(features),Path(output)
    raw=(features/'features.jsonl').read_bytes()
    parent=json.loads((features/'manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=parent['features_sha256']:raise ValueError('parent digest mismatch')
    records=[]
    for line in raw.splitlines():
        row=json.loads(line);target,reason=label(row)
        records.append(dict(trial_id=row['trial_id'],window_end=row['window_end'],split=row['split'],
                            candidate_target=target,reason=reason,original_episode_target=row['original_episode_target'],
                            source_history_sha256=row['input_history_sha256'],annotation_basis=CONTRACT['annotation_basis']))
    data=''.join(json.dumps(r,sort_keys=True)+'\n' for r in records).encode()
    digest=hashlib.sha256(data).hexdigest()
    output.mkdir(parents=True,exist_ok=False)
    (output/'labels.jsonl').write_bytes(data)
    (output/'contract.json').write_text(json.dumps(CONTRACT,indent=2)+'\n')
    manifest=dict(dataset_id='b-proxy-v1-'+digest[:16],label_sha256=digest,parent_features_sha256=parent['features_sha256'],
                  contract_sha256=hashlib.sha256((output/'contract.json').read_bytes()).hexdigest(),
                  generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  counts=dict(Counter('unknown' if r['candidate_target'] is None else str(r['candidate_target']).lower() for r in records)),
                  use='engineering proxy experiment only',human_signed=False)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lock=dict(schema='b-training-plan-v1',status='pre-registered-no-training-run',label_manifest_sha256=hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest(),
              parent_features_sha256=parent['features_sha256'],split_sha256=parent['split_sha256'],
              task='proxy approximation only; no true-occupancy accuracy or ML benefit claim',
              candidates=[dict(max_depth=d,min_samples_leaf=2,criterion='gini',tie_break='positive') for d in (1,2)],
              fitting='train only; non-UNKNOWN labels and eligible complete vectors; no imputation, scaling or class reweighting',
              selection='validation only: minimize per-trial mean window 0/1 error; equal trial weight; ties choose smaller depth',
              prediction='existing ml.predict positive-majority rule; no threshold search',
              validation_rejections='report separately with full denominator; never silently drop in report',
              final_refit=False,test_policy='development test evaluated only after model/config lock; no tuning on test; no independent-test claim',
              random_seed=None,determinism='existing deterministic CART',methods='C0-C3 same publication, quality accounting and proxy target; original episode truth separate',
              remaining_gate='P2 loader must verify all hashes and feature allowlist; persist chosen model hash before development-test evaluation')
    (output/'training_plan.lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--features',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(publish(a.features,a.output)))
