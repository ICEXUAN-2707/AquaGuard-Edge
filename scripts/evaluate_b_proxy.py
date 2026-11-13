"""P3: unchanged production-shaped C0-C3 on locked proxy development holdout."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from train_b_proxy import ROOT,checked,sha
from b_training_inputs import verify_inputs
from b_bundle_checks import check_annotations
from experiment.config import MODEL_FEATURE_NAMES
from experiment.methods import c0_threshold,c1_instant,c2_rules,c3_shadow
from experiment.ml import load_model
from alignment import align
from checkpoint import save
from rules import classify

METHODS=('C0','C1','C2','C3')
def ratio(a,b):return a/b if b else None

def metrics(rows,method):
    positive=[r for r in rows if r['target'] is True]
    negative=[r for r in rows if r['target'] is False]
    unknown=[r for r in rows if r['target'] is None]
    def count(group,value):return sum(r['methods'][method]['value'] is value for r in group)
    tp,fn,rp=count(positive,True),count(positive,False),count(positive,None)
    fp,tn,rn=count(negative,True),count(negative,False),count(negative,None)
    return dict(n=len(rows),positive=len(positive),negative=len(negative),unknown_required=len(unknown),
                tp=tp,fn=fn,fp=fp,tn=tn,rejected_positive=rp,rejected_negative=rn,
                precision=ratio(tp,tp+fp),recall=ratio(tp,len(positive)),false_positive_rate=ratio(fp,len(negative)),
                rejection_rate_known=ratio(rp+rn,len(positive)+len(negative)),
                rejection_rate_all=ratio(sum(r['methods'][method]['value'] is None for r in rows),len(rows)),
                unknown_correct_refusals=count(unknown,None),unknown_positive_outputs=count(unknown,True),unknown_negative_outputs=count(unknown,False),
                detection_delay_sec=None,delay_reason='independent event onset unavailable',
                null_ratio_reason='zero denominator where ratio is null')

def evaluate(features,labels,model_dir,output):
    features,labels,model_dir,output=map(Path,(features,labels,model_dir,output))
    protocol=ROOT/'deliverables/B-PROXY-MODEL-001/P3_PROTOCOL.json'
    spec=json.loads(protocol.read_text(encoding='utf-8-sig'))
    lock=json.loads((model_dir/'model.lock.json').read_text())
    checked(model_dir/'model.json',lock['model_sha256']);load_model(model_dir/'model.json')
    plan_raw=checked(labels/'training_plan.lock.json',lock['plan_sha256']);plan=json.loads(plan_raw)
    lm=json.loads(checked(labels/'manifest.json',plan['label_manifest_sha256']))
    checked(labels/'contract.json',lm['contract_sha256'])
    fr=[json.loads(l) for l in checked(features/'features.jsonl',plan['parent_features_sha256']).splitlines()]
    fm=json.loads(checked(features/'manifest.json',plan['feature_manifest_sha256']))
    verify_inputs(ROOT,fm,plan,fr)
    annotations=[json.loads(l) for l in checked(labels/'labels.jsonl',lm['label_sha256']).splitlines()]
    index=check_annotations(fr,annotations)
    source=ROOT/'deliverables/B-SIM-001'
    trials={t['trial_id']:t for t in json.loads((source/'trials.json').read_text())['trials']}
    streams=defaultdict(list)
    for line in gzip.decompress((source/'observations.jsonl.gz').read_bytes()).splitlines():
        item=json.loads(line);streams[item['trial_id']].append(item['observation'])
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    for row in fr:
        if row['split']!='test':continue
        identity=row['trial_id'];end=datetime.fromisoformat(row['window_end']);now=datetime.fromisoformat(row['published_at'])
        history=[r for r in streams[identity] if datetime.fromisoformat(r['received_at'])<=now and datetime.fromisoformat(r['event_time'])<=end]
        if sha(json.dumps(history,sort_keys=True,allow_nan=False).encode())!=row['input_history_sha256']:raise ValueError('history digest mismatch')
        window=align(history,[end],**fm['config'])['windows'][0]
        root=output/'checkpoints'/identity
        fw=save(root,window,history,alignment_config=fm['config'])
        if {n:fw['features'][n] for n in MODEL_FEATURE_NAMES}!=row['features']:raise ValueError('feature replay mismatch')
        assessment=classify(fw,now,checkpoint_root=root)
        methods={'C0':c0_threshold(window,min_flow_coverage=.8),
                 'C1':c1_instant(window,min_flow_coverage=.8,min_presence_coverage=.8),
                 'C2':c2_rules(assessment)}
        methods['C3']=c3_shadow(fw,checkpoint_root=root,now=now,rules_prediction=methods['C2'],model_path=model_dir/'model.json')
        if methods['C3'].get('fallback'):raise ValueError('valid locked model unexpectedly fell back')
        ann=index[(identity,row['window_end'])]
        if ann['split']!='test':raise ValueError('label split mismatch')
        records.append(dict(trial_id=identity,cohort_id=trials[identity]['cohort_id'],scenario=trials[identity]['scenario'],window_end=row['window_end'],
                            target=ann['candidate_target'],episode_target=ann['original_episode_target'],methods=methods))
    primary=[r for r in records if datetime.fromisoformat(r['window_end']).second==40]
    if len(primary)!=18 or len(records)!=54:raise ValueError('development holdout count mismatch')
    failures=[]
    for r in records:
        for method in METHODS:
            value=r['methods'][method]['value'];target=r['target']
            if value is not target:
                failures.append(dict(trial_id=r['trial_id'],window_end=r['window_end'],scenario=r['scenario'],method=method,target=target,output=value,reason=r['methods'][method]['reason']))
    report=dict(schema='b-proxy-p3-report-v1',protocol=spec,protocol_sha256=sha(protocol.read_bytes()),model_sha256=lock['model_sha256'],
                runner_sha256=sha(Path(__file__).read_bytes()),label_sha256=lm['label_sha256'],predictions_sha256=sha(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records).encode()),test_evaluated=True,
                primary={m:metrics(primary,m) for m in METHODS},secondary_windows={m:metrics(records,m) for m in METHODS},
                reasons={m:dict(Counter(r['methods'][m]['reason'] for r in records)) for m in METHODS},
                scenarios={s:{m:metrics([r for r in primary if r['scenario']==s],m) for m in METHODS} for s in sorted({r['scenario'] for r in primary})},
                failures=failures,limitations=['proxy labels are rule-derived','development holdout previously exposed','overlapping windows not independent','C3 native quality gate may use water quality; water is excluded from model vector; no safety path changes','no independent onset: delay not estimable'])
    (output/'predictions.jsonl').write_bytes(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records).encode())
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('features','labels','model-dir','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();r=evaluate(a.features,a.labels,a.model_dir,a.output);print(json.dumps(r['primary'],indent=2))
