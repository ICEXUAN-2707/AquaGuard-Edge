"""P4 adapter-level fault injection; immutable model and checkpoints."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from train_b_proxy import ROOT,checked
from checkpoint import restore
from rules import classify
from experiment.methods import c2_rules,c3_shadow


def run(checkpoints,model_dir,output):
    checkpoints,model_dir,output=map(Path,(checkpoints,model_dir,output))
    lock=json.loads((model_dir/'model.lock.json').read_text())
    model_raw=checked(model_dir/'model.json',lock['model_sha256'])
    model=json.loads(model_raw)
    output.mkdir(parents=True,exist_ok=False)
    corrupted=output/'corrupt.json';corrupted.write_text('{invalid')
    wrong=output/'wrong-version.json';wrong.write_text(json.dumps(dict(model,feature_version='incompatible')))
    variants={'missing':output/'absent.json','corrupt':corrupted,'wrong_version':wrong}
    expected={'missing':'FALLBACK_MODEL_MISSING','corrupt':'FALLBACK_MODEL_CORRUPT','wrong_version':'FALLBACK_MODEL_VERSION_MISMATCH'}
    records=[]
    paths=sorted(checkpoints.glob('*/*.json'))
    if len(paths)!=54:raise ValueError('expected 54 saved development windows')
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for path in paths:
        saved=restore(path);fw=saved['feature_window'];window=saved['last_window']
        now=datetime.fromisoformat(window['published_at'])
        fixed=c2_rules(classify(fw,now,checkpoint_root=path.parent))
        for variant,model_path in variants.items():
            result=c3_shadow(fw,checkpoint_root=path.parent,now=now,rules_prediction=fixed,model_path=model_path)
            passed=(result['value'] is fixed['value'] and result['fallback'] is True and result['shadow'] is True and result['reason']==expected[variant])
            if not passed:raise ValueError('fallback diverged from fixed C2')
            records.append(dict(trial_id=path.parent.name,window_end=window['window_end'],variant=variant,
                                c2_value=fixed['value'],fallback_value=result['value'],reason=result['reason'],passed=passed))
    if before!={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:raise ValueError('checkpoint modified')
    checked(model_dir/'model.json',lock['model_sha256'])
    report=dict(schema='b-proxy-p4-fallback-v1',windows=len(paths),trials=len({r['trial_id'] for r in records}),
                checks=len(records),all_passed=True,by_variant=dict(Counter(r['variant'] for r in records)),
                immutable_model_and_checkpoints=True,scope='existing C3 adapter over P3 saved snapshots; no live service or hardware safety test',
                records=records)
    (output/'fallback_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return {k:v for k,v in report.items() if k!='records'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoints','model-dir','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(run(a.checkpoints,a.model_dir,a.output),indent=2))
