"""Post-hoc paired audit and future-study planning, not a superiority claim."""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

def required_pairs(expected_gain,required_gain,discordance,power=.8,alpha=.025):
    if not 0<=required_gain<expected_gain<=discordance<=1:raise ValueError('invalid paired alternative')
    z=NormalDist().inv_cdf(1-alpha);zp=NormalDist().inv_cdf(power)
    return math.ceil((z*math.sqrt(discordance-required_gain**2)+zp*math.sqrt(discordance-expected_gain**2))**2/(expected_gain-required_gain)**2)

def event(row,method,metric):
    p=row['methods'][method]['value'];t=row['target']
    if metric=='false_positive':return int(p is True) if t is False else None
    if metric=='miss_including_refusal':return int(p is not True) if t is True else None
    if metric=='refusal_all':return int(p is None)
    raise ValueError('unknown metric')

def compare(rows):
    result={}
    for metric in ('false_positive','miss_including_refusal','refusal_all'):
        selected=[r for r in rows if event(r,'C2',metric) is not None]
        diffs=[event(r,'C2',metric)-event(r,'C3',metric) for r in selected]
        result[metric]=dict(n=len(diffs),c2_events=sum(event(r,'C2',metric) for r in selected),
                            c3_events=sum(event(r,'C3',metric) for r in selected),
                            benefit=sum(diffs)/len(diffs) if diffs else None,
                            c3_better=sum(d>0 for d in diffs),c3_worse=sum(d<0 for d in diffs),
                            paired_effect_ci=None,ci_reason='exposed synthetic convenience sample with clustered dependence; no population CI justified')
    return result

def run(predictions,output):
    raw=Path(predictions).read_bytes();rows=[json.loads(l) for l in raw.splitlines()]
    primary=[r for r in rows if datetime.fromisoformat(r['window_end']).second==40]
    if len(primary)!=18 or len({r['trial_id'] for r in primary})!=18:raise ValueError('primary inventory mismatch')
    result=dict(schema='b-posthoc-paired-audit-v1',predictions_sha256=hashlib.sha256(raw).hexdigest(),
                status='post-hoc analysis; no retrospective pre-registration',
                primary=compare(primary),secondary_overlapping_windows=compare(rows),
                uncertainty=dict(primary_discordant_trials=sum(r['methods']['C2']['value'] is not r['methods']['C3']['value'] for r in primary),
                                 nominal_cohorts=3,source_linked_components=2,
                                 explanation='cohort-003 and cohort-004 linked by identical source observations; not 18 independent trials',
                                 conditional_zero_discordance_upper95=1-.05**(1/2),
                                 conditional_bound_scope='illustration only: assumes 2 independent identically distributed random source groups, not established here; bounds group-level any disagreement, not FPR or causal benefit',
                                 conclusion='no demonstrated improvement; zero observed difference does not establish equivalence'),
                future_planning=dict(status='proposal for new data only; not applied to current results',
                    primary='C2 FPR minus C3 FPR; require lower one-sided 97.5% paired CI > 0.05',
                    safeguards='upper one-sided 97.5% bounds on extra missed-positive rate (including refusals) and extra refusal rate <= 0.02; hierarchical pre-specified conjunction',
                    delay='secondary descriptive until independently annotated onset and censoring policy fixed',
                    design='one eligible negative pair per independent group for approximation; plan positive and quality strata separately',
                    scenarios=[dict(expected_gain=.10,required_gain=.05,discordance=q,power=.8,alpha=.025,approx_independent_negative_pairs=required_pairs(.10,.05,q)) for q in (.12,.2,.3)],
                    formula='normal approximation for paired {-1,0,1} outcome; N=(z(1-alpha)*sqrt(q-margin^2)+z(power)*sqrt(q-delta^2))^2/(delta-margin)^2',
                    caveats='planning approximation only; q and baseline FPR need independent pilot; cluster design effects/positive-stratum power/attrition require separate simulation before final recruitment',
                    zero_event_example=dict(rate_upper=.05,alpha=.05,independent_units=math.ceil(math.log(.05)/math.log(.95)),interpretation='zero-event rate precision only; not proof of paired superiority')))
    with Path(output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--predictions',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=run(a.predictions,a.output);print(json.dumps({'primary':r['primary'],'planning':r['future_planning']['scenarios']},indent=2))
