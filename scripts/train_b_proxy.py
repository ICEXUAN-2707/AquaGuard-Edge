"""Locked train/validation proxy experiment. Test predictions are forbidden here."""
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'spikes/SP-04'))
from experiment.config import MODEL_FEATURE_NAMES
from experiment.ml import train,predict,write_model,load_model
from b_training_inputs import verify_inputs

def sha(data):return hashlib.sha256(data).hexdigest()
def checked(path,digest):
    raw=Path(path).read_bytes()
    if sha(raw)!=digest:raise ValueError('digest mismatch: '+str(path))
    return raw

def run(features,labels,output,source=None,split_path=None):
    features,labels,output=map(Path,(features,labels,output))
    plan_raw=(labels/'training_plan.lock.json').read_bytes();plan=json.loads(plan_raw)
    lm=json.loads(checked(labels/'manifest.json',plan['label_manifest_sha256']))
    fm=json.loads((features/'manifest.json').read_text())
    raw=checked(features/'features.jsonl',plan['parent_features_sha256'])
    if fm['features_sha256']!=sha(raw) or fm['split_sha256']!=plan['split_sha256'] or lm['parent_features_sha256']!=sha(raw):raise ValueError('parent binding mismatch')
    checked(labels/'contract.json',lm['contract_sha256'])
    label_rows=[json.loads(l) for l in checked(labels/'labels.jsonl',lm['label_sha256']).splitlines()]
    feature_rows=[json.loads(l) for l in raw.splitlines()]
    input_checks=verify_inputs(ROOT,fm,plan,feature_rows,source,split_path)
    key=lambda r:(r['trial_id'],r['window_end'])
    index={key(r):r for r in label_rows}
    if len(index)!=len(label_rows) or len({key(r) for r in feature_rows})!=len(feature_rows) or set(index)!={key(r) for r in feature_rows}:raise ValueError('window inventory mismatch')
    sets=defaultdict(list);counts=defaultdict(lambda:dict(total=0,eligible=0,rejected=0));trial_split={}
    for row in feature_rows:
        annotation=index[key(row)];split=row['split']
        if split not in ('train','validation','test') or annotation['split']!=split:raise ValueError('split mismatch')
        if trial_split.setdefault(row['trial_id'],split)!=split:raise ValueError('trial leakage')
        if set(row['features'])!=set(MODEL_FEATURE_NAMES):raise ValueError('feature allowlist mismatch')
        counts[split]['total']+=1
        eligible=annotation['candidate_target'] is not None and not row['rejection_reasons']
        counts[split]['eligible' if eligible else 'rejected']+=1
        if eligible and split!='test':sets[split].append((row,annotation['candidate_target']))
    output.mkdir(parents=True,exist_ok=False)
    scores=[];models=[]
    for hp in plan['candidates']:
        metadata=dict(task=plan['task'],plan_sha256=sha(plan_raw),trial_ids=sorted({r['trial_id'] for r,y in sets['train']}),label_sha256=lm['label_sha256'])
        model=train([r['features'] for r,y in sets['train']],[int(y) for r,y in sets['train']],metadata=metadata,hyperparameters=hp)
        per_trial=defaultdict(list)
        for row,target in sets['validation']:
            prediction,_,_=predict(model,row['features'])
            per_trial[row['trial_id']].append(int(prediction!=target))
        if not per_trial:raise ValueError('no validation samples')
        error=sum((Fraction(sum(v),len(v)) for v in per_trial.values()),Fraction())/len(per_trial)
        scores.append(dict(hyperparameters=hp,validation_error=float(error),validation_error_fraction=str(error),validation_scored_trials=len(per_trial)))
        models.append(model)
    winner=min(range(len(scores)),key=lambda i:(Fraction(scores[i]['validation_error_fraction']),scores[i]['hyperparameters']['max_depth']))
    model_hash=write_model(output/'model.json',models[winner])
    if load_model(output/'model.json') != models[winner]:raise ValueError('model roundtrip mismatch')
    lock=dict(schema='b-trained-model-lock-v1',task=plan['task'],plan_sha256=sha(plan_raw),model_sha256=model_hash,
              selected=scores[winner],candidates=scores,window_accounting=dict(counts),test_evaluated=False,
              limitation='validation excludes UNKNOWN labels; full window accounting retained; proxy consistency only',
              input_checks=input_checks,model_roundtrip='PASS', runner_sha256=sha(Path(__file__).read_bytes()),input_validator_sha256=sha((ROOT/'scripts/b_training_inputs.py').read_bytes()))
    (output/'model.lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    return lock

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('features','labels','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(run(a.features,a.labels,a.output),indent=2))
