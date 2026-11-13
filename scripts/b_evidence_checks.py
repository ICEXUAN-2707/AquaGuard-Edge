"""Recompute archived evidence instead of trusting summary flags."""
from collections import Counter
from datetime import datetime

METHODS=('C0','C1','C2','C3')
VARIANTS={'missing':'FALLBACK_MODEL_MISSING','corrupt':'FALLBACK_MODEL_CORRUPT','wrong_version':'FALLBACK_MODEL_VERSION_MISMATCH'}

def check_evidence(records, report, fallback, annotations, model_hash, feature_manifest_hash):
    from evaluate_b_proxy import metrics
    key=lambda r:(r['trial_id'],datetime.fromisoformat(r['window_end']))
    index={key(r):r for r in annotations if r['split']=='test'}
    keys=[key(r) for r in records]
    if len(set(keys))!=len(keys) or set(keys)!=set(index):raise ValueError('prediction inventory mismatch')
    for row in records:
        label=index[key(row)]
        if row['target'] is not label['candidate_target'] or row['episode_target'] is not label['original_episode_target']:
            raise ValueError('prediction truth mismatch')
        if set(row['methods'])!=set(METHODS):raise ValueError('method inventory mismatch')
        for prediction in row['methods'].values():
            if prediction['value'] is not None and type(prediction['value']) is not bool:raise ValueError('invalid prediction type')
    primary=[r for r in records if datetime.fromisoformat(r['window_end']).second==40]
    for field,selected in (('primary',primary),('secondary_windows',records)):
        if report[field]!={m:metrics(selected,m) for m in METHODS}:raise ValueError('report metrics mismatch: '+field)
    expected_reasons={m:dict(Counter(r['methods'][m]['reason'] for r in records)) for m in METHODS}
    if report['reasons']!=expected_reasons:raise ValueError('reason counts mismatch')
    expected_scenarios={s:{m:metrics([r for r in primary if r['scenario']==s],m) for m in METHODS} for s in {r['scenario'] for r in primary}}
    if report['scenarios']!=expected_scenarios:raise ValueError('scenario metrics mismatch')
    expected_failures=[dict(trial_id=r['trial_id'],window_end=r['window_end'],scenario=r['scenario'],method=m,target=r['target'],output=r['methods'][m]['value'],reason=r['methods'][m]['reason']) for r in records for m in METHODS if r['methods'][m]['value'] is not r['target']]
    if report['failures']!=expected_failures:raise ValueError('failure evidence mismatch')
    if report['model_sha256']!=model_hash or fallback['model_sha256']!=model_hash or fallback['feature_manifest_sha256']!=feature_manifest_hash:
        raise ValueError('evidence model/source mismatch')
    if report.get('test_evaluated') is not True:raise ValueError('evaluation status mismatch')
    expected={(i,e,v) for i,e in keys for v in VARIANTS}
    checks=fallback['records'];actual=[(*key(r),r['variant']) for r in checks]
    if len(set(actual))!=len(actual) or set(actual)!=expected:raise ValueError('fallback inventory mismatch')
    c2={key(r):r['methods']['C2']['value'] for r in records}
    for row in checks:
        value=c2[key(row)]
        if row['passed'] is not True or row['c2_value'] is not value or row['fallback_value'] is not value or row['reason']!=VARIANTS[row['variant']]:raise ValueError('fallback value mismatch')
    if fallback['windows']!=len(records) or fallback['trials']!=len({r['trial_id'] for r in records}) or fallback['checks']!=len(expected) or fallback['by_variant']!={v:len(records) for v in VARIANTS} or fallback['all_passed'] is not True:
        raise ValueError('fallback summary mismatch')
    return len(checks)
