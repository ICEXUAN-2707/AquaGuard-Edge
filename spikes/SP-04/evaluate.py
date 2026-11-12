"""Finite synthetic binary candidate comparison, no real-world accuracy claims."""
import json,sys
from pathlib import Path
from datetime import timedelta
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from scenarios import observations,T
from gates import gate,DEFAULT
from alignment import align
from checkpoint import save
from rules import classify

def metrics(records,key):
    if not records:
        raise ValueError('evaluation requires at least one labeled record')
    if not isinstance(key,str) or not key:
        raise ValueError('explicit method identity required')
    out=dict(n=len(records),tp=0,fp=0,tn=0,fn=0,rejected_positive=0,rejected_negative=0)
    for r in records:
        if not isinstance(r,dict) or type(r.get('candidate_target')) is not bool:
            raise ValueError('candidate target must be a boolean')
        predictions=r.get('predictions')
        if not isinstance(predictions,dict) or key not in predictions:
            raise ValueError('method prediction missing')
        target=r['candidate_target'];prediction=predictions[key]
        if prediction is not None and type(prediction) is not bool:
            raise ValueError('prediction must be boolean or null')
        if prediction is None:out['rejected_positive' if target else 'rejected_negative']+=1
        else:out['tp' if target and prediction else 'fn' if target else 'fp' if prediction else 'tn']+=1
    out['rejection_rate']=(out['rejected_positive']+out['rejected_negative'])/out['n']
    positives=sum(r['candidate_target'] for r in records)
    out['positive_recall_all']=None if positives==0 else out['tp']/positives
    return out

def evaluate(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    trials=json.loads((BASE/'data/evaluation_trials.json').read_text(encoding='utf-8-sig'))
    records=[]
    for trial in trials:
        rows=observations(**trial['parameters'])
        window=align(rows,[T+timedelta(seconds=30)])['windows'][0]
        fw=save(output/'checkpoints',window,rows,alignment_config={})
        context=gate(fw,T+timedelta(seconds=32),checkpoint_root=output)
        flow=window['sensor_summary']['flow']
        b0=None if flow['state']=='unknown' or flow['coverage_ratio']<DEFAULT['min_flow_coverage'] else flow['state']=='active'
        b1=None if context['status']!='READY' else flow['state']=='active' and window['sensor_summary']['presence']['state']=='absent'
        predictions=dict(B0_flow=b0,B1_instant=b1)
        for threshold in (5,10,15):
            result=classify(fw,T+timedelta(seconds=32),checkpoint_root=output,config=dict(DEFAULT,unattended_sec=threshold))
            predictions[f'B2_{threshold}s']=None if result['situation']=='UNKNOWN' else result['situation']=='POSSIBLE_UNATTENDED_FLOW'
        records.append(dict(**trial,predictions=predictions))
    report=dict(scope='synthetic prototype_only; binary candidate task',records=records,metrics={k:metrics(records,k) for k in records[0]['predictions']})
    (output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return report

if __name__=='__main__':
    result=evaluate(BASE/'evidence/r05')
    print(json.dumps(result['metrics'],ensure_ascii=False))
