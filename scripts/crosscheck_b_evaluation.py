"""Independent source/replay/accounting cross-check for the existing B handoff."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def encoded(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def run(package,output,c_ref=None):
    package=Path(package).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    checks=[]
    def checked(name,condition):
        if not condition:raise ValueError('cross-check failed: '+name)
        checks.append({'name':name,'status':'PASS'})
    def load(name):return json.loads((package/name).read_text(encoding='utf-8'))
    report=load('evaluation.json');raw=load('raw/comparison.json')
    for source in report['versions']['source_files']:
        path=(ROOT/source['path']).resolve()
        checked('source:'+source['path'],path.is_relative_to(ROOT) and hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'])
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'spikes/SP-04'))
    from evaluate import evaluate
    from checkpoint import restore
    from alignment import align
    reproduced=evaluate(output/'recomputed')
    checked('raw source reevaluation equals package',encoded(reproduced)==encoded(raw))
    positives=sum(row['candidate_target'] for row in raw['records'])
    checked('known fixture scope',len(raw['records'])==8 and positives==3)
    methods={method['method_id']:method for method in report['methods']}
    for method_id in raw['metrics']:
        counts=Counter()
        for row in raw['records']:
            prediction=row['predictions'][method_id];target=row['candidate_target']
            if prediction is None:key='rejected_positive' if target else 'rejected_negative'
            elif prediction:key='tp' if target else 'fp'
            else:key='fn' if target else 'tn'
            counts[key]+=1
        actual=methods[method_id]
        checked('six-way accounting:'+method_id,all(actual['counts'][key]==counts[key] for key in ('tp','fp','tn','fn','rejected_positive','rejected_negative')) and sum(counts.values())==8)
        checked('recall denominator:'+method_id,actual['metrics']['positive_recall_all']['value']==counts['tp']/positives and actual['metrics']['positive_recall_all']['denominator']==positives)
        checked('abstention denominator:'+method_id,actual['metrics']['rejection_rate']['value']==(counts['rejected_positive']+counts['rejected_negative'])/8)
    trials=load('trials.json')['trials']
    observations=[json.loads(line) for line in (package/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
    for identity,trial in trials.items():
        rows=[entry['observation'] for entry in observations if entry['trial_id']==identity]
        restored=restore(package/trial['checkpoint_ref'])
        checked('checkpoint native replay:'+identity,encoded(restored['history'])==encoded(sorted(rows,key=lambda row:row['observation_id'])))
        from edge.contracts.models import _aware
        window=align(rows,[_aware(trial['window_end'])],**restored['alignment_config'])['windows'][0]
        checked('M3 versus checkpoint:'+identity,encoded(window)==encoded(restored['last_window']))
    grouped={identity:[item['observation'] for item in observations if item['trial_id']==identity] for identity in trials}
    checked('indistinguishable pair retained',grouped['synthetic-left20']==grouped['synthetic-hidden-person'] and trials['synthetic-left20']['candidate_target'] is True and trials['synthetic-hidden-person']['candidate_target'] is False)
    checked('no unearned acceptance',report['acceptance']['g3_passed'] is False and not report['dataset']['split']['held_out_test'] and report['unavailable_methods'][0]['availability']=='NOT_PROVIDED')
    if c_ref:
        # Read one pinned repository blob; never switch or edit C's worktree.
        code=subprocess.check_output(['git','show',c_ref+':spikes/C-business/evaluations.py'],cwd=ROOT)
        adapter=output/'c_reference_adapter.py';adapter.write_bytes(code)
        sys.path.insert(0,str(ROOT/'spikes/C-business'))
        spec=importlib.util.spec_from_file_location('c_crosscheck_adapter',adapter)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        imported=module.load_legacy(package/'raw/comparison.json',package,'B-EVAL-001-reference')
        checked('C legacy adapter preserves records',encoded(imported['records'])==encoded(raw['records']))
        checked('C legacy adapter preserves metrics',encoded(imported['metrics'])==encoded(raw['metrics']))
        checked('C adapter retains simulation scope',imported['source']=='simulation' and imported['task']=='binary_candidate' and imported['trial_count']==8)
    result={'status':'PASS','checked_at':datetime.now(timezone.utc).isoformat(),
            'checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'evaluation_id':report['evaluation_id'],'c_reference':c_ref,'checks':checks,
            'limits':['Automated same-agent cross-check, not independent human sign-off.',
                      'Eight synthetic development cases; no ML, real-world accuracy or G3 acceptance.',
                      'C check covers only pinned legacy import, not deployed HTTP or final branch integration.']}
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'PASS','checks':len(checks),'evaluation_id':report['evaluation_id'],'c_reference':c_ref}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=ROOT/'deliverables/B-EVAL-001')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--c-ref')
    args=parser.parse_args()
    print(json.dumps(run(args.package,args.output,args.c_ref),ensure_ascii=False))
