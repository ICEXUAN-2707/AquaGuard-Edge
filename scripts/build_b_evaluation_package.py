"""Package existing B synthetic results without changing algorithms or public DTOs."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'aquaguard-b-evaluation-draft-1'
METHODS = {
    'B0_flow': ('C0', '水流阈值', None),
    'B1_instant': ('C1', '即时多源规则', None),
    'B2_5s': ('C2', '时序规则 · 5 秒', 5),
    'B2_10s': ('C2', '时序规则 · 10 秒', 10),
    'B2_15s': ('C2', '时序规则 · 15 秒', 15),
}
COUNTS = ('tp', 'fp', 'tn', 'fn', 'rejected_positive', 'rejected_negative')
LIMITS = [
    'Only eight hand-constructed synthetic scenarios, one evaluated window per trial; no population generalization.',
    'No held-out test split; scenario thresholds were examined on this set. This is a development diagnostic set.',
    'Candidate labels are synthetic operation annotations, not sensor-proven absence or real incident labels.',
    'Hidden-person and left20 scenarios deliberately have identical observations and different targets.',
    'No trained ML, real hardware, real response latency or cloud acceptance is included.',
    'Observation IDs repeat across trials: identity is scoped by trial_id. Do not merge trials into a live device stream.',
    'C0-C2 presentation mapping is a proposal pending B review; original B method IDs remain authoritative.',
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def outcome(target, prediction):
    if prediction is None:
        return 'rejected_positive' if target else 'rejected_negative'
    if type(prediction) is not bool or type(target) is not bool:
        raise ValueError('binary targets and predictions required')
    return ('tp' if prediction else 'fn') if target else ('fp' if prediction else 'tn')


def source_inventory():
    paths = [ROOT/'spikes/SP-04/evaluate.py', ROOT/'spikes/SP-04/data/evaluation_trials.json',
             ROOT/'spikes/SP-04/data/rules_config.json', ROOT/'edge/contracts/models.py']
    for folder in ('SP-03', 'SP-03-features', 'SP-04'):
        paths.extend((ROOT/'spikes'/folder/'src').glob('*.py'))
    return [{'path':p.relative_to(ROOT).as_posix(), 'sha256':digest(p.read_bytes())} for p in sorted(paths)]


def build(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)  # Preserve previous evidence.
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT/'spikes/SP-04'))
    from evaluate import evaluate
    from scenarios import observations, T
    from alignment import align, ALGORITHM_VERSION
    from checkpoint import save, FEATURE_VERSION, FORMAT
    from gates import DEFAULT, gate
    from rules import classify, SEMANTIC_VERSION

    raw_dir = output/'raw'
    original = evaluate(raw_dir)
    write_json(raw_dir/'comparison.json', original)
    inventory = source_inventory()
    trials, predictions, review, observation_lines = {}, [], [], []
    for record in original['records']:
        trial_id = record['trial_id']
        rows = observations(**record['parameters'])
        observation_lines.extend({'trial_id':trial_id, 'observation':r} for r in rows)
        window = align(rows, [T+timedelta(seconds=30)])['windows'][0]
        feature = save(raw_dir/'checkpoints', window, rows, alignment_config={})
        checkpoint_ref = Path(feature['state_checkpoint_ref']).relative_to(output).as_posix()
        context = gate(feature, T+timedelta(seconds=32), checkpoint_root=raw_dir)
        trials[trial_id] = {
            'trial_id':trial_id, 'source':'simulation', 'operation':record['operation'],
            'candidate_target':record['candidate_target'], 'parameters':record['parameters'],
            'label_basis':'hand-authored synthetic operation annotation',
            'window_id':window['window_id'], 'window_end':window['window_end'],
            'checkpoint_ref':checkpoint_ref, 'observation_count':len(rows),
            'quality_gate':{'status':context['status'], 'reason':context['reason'], 'data_quality':context['data_quality']},
        }
        for method_id, (_, _, threshold) in METHODS.items():
            prediction = record['predictions'][method_id]
            status = outcome(record['candidate_target'], prediction)
            item = {'trial_id':trial_id, 'method_id':method_id, 'candidate_target':record['candidate_target'],
                    'prediction':prediction, 'outcome':status, 'checkpoint_ref':checkpoint_ref,
                    'observation_scope':{'trial_id':trial_id, 'observation_ids':[r['observation_id'] for r in rows]}}
            if threshold is not None:
                assessment = classify(feature, T+timedelta(seconds=32), checkpoint_root=raw_dir,
                                      config=dict(DEFAULT, unattended_sec=threshold))
                derived = None if assessment['situation']=='UNKNOWN' else assessment['situation']=='POSSIBLE_UNATTENDED_FLOW'
                if derived != prediction:
                    raise ValueError('normalization changed a B prediction')
                item['assessment'] = assessment
            else:
                item['explanation'] = ('flow terminal state with coverage gate' if method_id=='B0_flow'
                                       else 'quality gate then terminal flow/presence states')
            predictions.append(item)
            if status in ('fp', 'fn', 'rejected_positive', 'rejected_negative'):
                review.append({'case_id':f'{trial_id}:{method_id}', 'trial_id':trial_id, 'method_id':method_id,
                               'category':status, 'operation':record['operation'], 'candidate_target':record['candidate_target'],
                               'prediction':prediction, 'checkpoint_ref':checkpoint_ref,
                               'interpretation':'Rejected evidence is not a confirmed correct negative.' if prediction is None
                                                else 'Candidate decision disagrees with the synthetic operation target.'})

    write_json(output/'trials.json', {'trials':trials})
    write_json(output/'review_cases.json', {
        'scope':'diagnostic errors and abstentions, not real incidents', 'cases':review,
        'indistinguishable_pair':['synthetic-left20', 'synthetic-hidden-person'],
        'pair_explanation':'Identical sensor observations cannot establish which operation annotation is true.',
    })
    for name, records in [('observations.jsonl', observation_lines), ('predictions.jsonl', predictions)]:
        (output/name).write_text(''.join(canonical(r).decode('utf-8')+'\n' for r in records), encoding='utf-8')
    dataset_hash = digest(canonical({'trials':original['records'], 'observations':observation_lines}))
    evaluation_id = 'b-synthetic-8-'+digest(canonical({'dataset':dataset_hash, 'sources':inventory, 'schema':VERSION}))[:16]
    positives = sum(r['candidate_target'] for r in original['records'])
    methods = []
    for method_id, (slot, title, threshold) in METHODS.items():
        metrics = original['metrics'][method_id]
        methods.append({
            'method_id':method_id, 'title':title, 'presentation_slot_proposal':slot,
            'mapping_status':'PENDING_B_REVIEW', 'availability':'AVAILABLE',
            'configuration':{'unattended_sec':threshold} if threshold is not None else {},
            'counts':{key:metrics[key] for key in ('n',)+COUNTS},
            'metrics':{
                'positive_recall_all':{'value':metrics['positive_recall_all'], 'unit':'fraction',
                                       'numerator':metrics['tp'], 'denominator':positives},
                'rejection_rate':{'value':metrics['rejection_rate'], 'unit':'fraction',
                                  'numerator':metrics['rejected_positive']+metrics['rejected_negative'],
                                  'denominator':metrics['n']},
            },
        })
    report = {
        'package_schema_version':VERSION, 'evaluation_id':evaluation_id, 'status':'NORMALIZED_DRAFT',
        'acceptance':{'b_owner_review':'PENDING', 'independent_review':'PENDING', 'g3_passed':False},
        'generated_at':datetime.now(timezone.utc).isoformat(), 'source':'simulation',
        'task':{'id':'binary-unattended-flow-candidate',
                'description':'Binary candidate decision versus synthetic operation annotation; not proof of actual absence.',
                'positive_label':'candidate_target=true', 'prediction_null':'abstention / UNKNOWN'},
        'dataset':{'sha256':dataset_hash, 'trial_count':len(trials), 'evaluated_windows':len(trials),
                   'positive_trials':positives, 'negative_trials':len(trials)-positives,
                   'raw_observation_records':len(observation_lines), 'identity_scope':'trial_id + observation identity',
                   'split':{'status':'NOT_SPLIT', 'role':'development_diagnostic', 'held_out_test':False}},
        'versions':{'alignment':ALGORITHM_VERSION, 'features':FEATURE_VERSION,
                    'checkpoint':FORMAT, 'rules_semantic':SEMANTIC_VERSION,
                    'alignment_configuration':align([],[])['config'],
                    'runtime':{'python':sys.version.split()[0], 'pydantic':version('pydantic')},
                    'rules_configuration':DEFAULT,
                    'checkout_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    'builder_sha256':digest(Path(__file__).read_bytes()), 'source_files':inventory},
        'metric_definitions':{
            'counts':'Exactly one terminal binary candidate per trial/method. TP/FP/TN/FN exclude abstentions.',
            'positive_recall_all':'TP / all positive trials, including rejected positives in the denominator.',
            'rejection_rate':'(rejected_positive + rejected_negative) / all trials.',
            'no_event_metric':'FP here counts trial-level predictions, not M6 alarm events or false alarms per hour.',
        },
        'methods':methods,
        'unavailable_methods':[{'presentation_slot_proposal':'C3', 'availability':'NOT_PROVIDED',
                                'reason':'No trained ML or model evaluation in the source experiment.'}],
        'unavailable_metrics':{
            'macro_f1':{'value':None, 'reason':'Not computed by the source evaluator; abstention policy not agreed.'},
            'response_latency_ms':{'value':None, 'reason':'Fixed logical evaluation time is not measured runtime latency.'},
            'false_alarms_per_hour':{'value':None, 'reason':'No measured duration or event-matching experiment.'},
        },
        'limitations':LIMITS,
        'evidence':{'raw_comparison':'raw/comparison.json', 'trials':'trials.json',
                    'observations':'observations.jsonl', 'predictions':'predictions.jsonl', 'review_cases':'review_cases.json'},
    }
    write_json(output/'evaluation.json', report)
    (output/'README.md').write_text(
        '# B 第一版规范化仿真评估包\n\n'
        '这是现有 8 个手工合成场景的开发诊断结果，不是独立测试集或真实性能报告。\n'
        '原始 B 方法 ID、预测和计数保持不变；C0–C2 映射待 B 确认，C3 未提供。\n'
        '拒判单列，不能当作正确负例；逻辑发布时间不能用于真实延迟结论。\n\n'
        'evaluation.json：规范化报告与指标定义。trials.json：场景、标签依据和检查点。\n'
        'observations.jsonl：以 trial_id 隔离的原始合成观测，不能直接合并为在线数据流。\n'
        'predictions.jsonl：逐场景/方法预测。review_cases.json：误判和拒判审查案例。\n'
        'raw/comparison.json：原 B 结果。raw/checkpoints：内容寻址、可重算的原生快照。\n'
        'manifest.json：除自身外所有文件的大小与 SHA256；不等于独立签署。\n\n'
        '从仓库执行：python scripts/build_b_evaluation_package.py --output <全新目录>\n'
        '核验：python scripts/build_b_evaluation_package.py --verify <包目录>\n'
        '每次生成新目录，不覆盖旧证据。时间和 checkout_commit 可以变化；源文件哈希和数据确定报告身份。\n'
        '本包不是公共 DTO/API 契约；供 B/C 确认格式与受控接口后接入现有实验页。\n', encoding='utf-8')
    manifest = {'format':'sha256-package-manifest-v1', 'evaluation_id':evaluation_id, 'files':[]}
    for p in sorted(output.rglob('*')):
        if p.is_file():
            manifest['files'].append({'path':p.relative_to(output).as_posix(), 'bytes':p.stat().st_size, 'sha256':digest(p.read_bytes())})
    write_json(output/'manifest.json', manifest)
    return verify(output)


def verify(output):
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    entries = manifest['files']
    names = [entry['path'] for entry in entries]
    if len(names)!=len(set(names)):
        raise ValueError('duplicate manifest path')
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.name!='manifest.json'}
    if actual != set(names):
        raise ValueError('manifest inventory mismatch')
    for entry in entries:
        p = (output/entry['path']).resolve()
        if not p.is_relative_to(output):
            raise ValueError('evidence path outside package')
        if not p.is_file() or p.stat().st_size!=entry['bytes'] or digest(p.read_bytes())!=entry['sha256']:
            raise ValueError('evidence digest mismatch: '+entry['path'])
    report = json.loads((output/'evaluation.json').read_text(encoding='utf-8'))
    raw = json.loads((output/'raw/comparison.json').read_text(encoding='utf-8'))
    if report['package_schema_version']!=VERSION or report['evaluation_id']!=manifest['evaluation_id']:
        raise ValueError('report identity mismatch')
    records = raw['records']
    if report['source']!='simulation' or report['dataset']['trial_count']!=len(records):
        raise ValueError('dataset scope mismatch')
    method_ids=[method['method_id'] for method in report['methods']]
    if len(method_ids)!=len(set(method_ids)) or set(method_ids)!=set(METHODS) or set(raw['metrics'])!=set(METHODS):
        raise ValueError('method inventory mismatch')
    record_ids=[record['trial_id'] for record in records]
    if len(record_ids)!=len(set(record_ids)):
        raise ValueError('duplicate raw trial')
    for record in records:
        if type(record['candidate_target']) is not bool or set(record['predictions'])!=set(METHODS):
            raise ValueError('invalid raw target or prediction inventory')
        for prediction in record['predictions'].values():
            if prediction is not None and type(prediction) is not bool:
                raise ValueError('invalid raw prediction')
    for method in report['methods']:
        method_id = method['method_id']
        counts = Counter(outcome(r['candidate_target'],r['predictions'][method_id]) for r in records)
        for key in COUNTS:
            if method['counts'][key]!=counts[key] or raw['metrics'][method_id][key]!=counts[key]:
                raise ValueError('prediction accounting mismatch')
        if method['counts']['n']!=len(records):
            raise ValueError('sample count mismatch')
        for name, metric in method['metrics'].items():
            if metric['unit']!='fraction' or metric['value']!=raw['metrics'][method_id][name]:
                raise ValueError('metric value mismatch')
            expected_numerator = counts['tp'] if name=='positive_recall_all' else counts['rejected_positive']+counts['rejected_negative']
            expected_denominator = sum(r['candidate_target'] for r in records) if name=='positive_recall_all' else len(records)
            if metric['numerator']!=expected_numerator or metric['denominator']!=expected_denominator:
                raise ValueError('metric denominator mismatch')
            if metric['value']!=expected_numerator/expected_denominator:
                raise ValueError('metric arithmetic mismatch')
    trials = json.loads((output/'trials.json').read_text(encoding='utf-8'))['trials']
    if set(trials)!=set(record_ids):
        raise ValueError('trial inventory mismatch')
    for record in records:
        trial=trials[record['trial_id']]
        for key in ('trial_id','operation','candidate_target','parameters'):
            if trial[key]!=record[key] or type(trial[key]) is not type(record[key]):
                raise ValueError('trial label/provenance mismatch')
        if trial['source']!='simulation':
            raise ValueError('trial source mismatch')
    observations=[json.loads(line) for line in (output/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
    grouped={trial_id:[] for trial_id in trials}
    for item in observations:
        if item['trial_id'] not in grouped or item['observation']['source']!='simulation':
            raise ValueError('observation scope mismatch')
        grouped[item['trial_id']].append(item['observation'])
    for trial_id, rows in grouped.items():
        if len(rows)!=trials[trial_id]['observation_count'] or len({row['observation_id'] for row in rows})!=len(rows):
            raise ValueError('observation identity/count mismatch')
    positives=sum(record['candidate_target'] for record in records)
    dataset=report['dataset']
    if (dataset['positive_trials'],dataset['negative_trials'],dataset['evaluated_windows'],dataset['raw_observation_records'])!=(positives,len(records)-positives,len(records),len(observations)):
        raise ValueError('dataset accounting mismatch')
    if dataset['sha256']!=digest(canonical({'trials':records,'observations':observations})):
        raise ValueError('dataset digest mismatch')
    expected = {(r['trial_id'], key):(r['candidate_target'], prediction)
                for r in records for key, prediction in r['predictions'].items()}
    normalized = [json.loads(line) for line in (output/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    seen = set()
    for row in normalized:
        key=(row['trial_id'], row['method_id'])
        if key in seen or expected.get(key)!=(row['candidate_target'],row['prediction']):
            raise ValueError('normalized prediction mismatch')
        if row['outcome']!=outcome(row['candidate_target'],row['prediction']):
            raise ValueError('normalized outcome mismatch')
        trial=trials[row['trial_id']]
        scope=row['observation_scope']
        if row['checkpoint_ref']!=trial['checkpoint_ref'] or scope!={'trial_id':row['trial_id'],'observation_ids':[r['observation_id'] for r in grouped[row['trial_id']]]}:
            raise ValueError('prediction evidence mismatch')
        seen.add(key)
    if seen!=set(expected):
        raise ValueError('prediction inventory mismatch')
    cases=json.loads((output/'review_cases.json').read_text(encoding='utf-8'))['cases']
    expected_cases={(r['trial_id'],r['method_id'],r['outcome']) for r in normalized if r['outcome'] in ('fp','fn','rejected_positive','rejected_negative')}
    actual_cases={(r['trial_id'],r['method_id'],r['category']) for r in cases}
    if actual_cases!=expected_cases or len(cases)!=len(actual_cases):
        raise ValueError('review case mismatch')
    for case in cases:
        trial=trials[case['trial_id']]
        target,prediction=expected[(case['trial_id'],case['method_id'])]
        if (case['candidate_target'],case['prediction'],case['operation'],case['checkpoint_ref'])!=(target,prediction,trial['operation'],trial['checkpoint_ref']):
            raise ValueError('review label/evidence mismatch')
    for trial in trials.values():
        ref=trial['checkpoint_ref']
        if ref not in names:
            raise ValueError('missing checkpoint')
        p=output/ref
        if p.stem!=digest(p.read_bytes()):
            raise ValueError('checkpoint identity mismatch')
        payload=json.loads(p.read_text(encoding='utf-8'))
        if canonical(payload['history'])!=canonical(sorted(grouped[trial['trial_id']],key=lambda r:r['observation_id'])):
            raise ValueError('checkpoint observation mismatch')
        if payload['window']['window_id']!=trial['window_id'] or payload['window']['window_end']!=trial['window_end']:
            raise ValueError('checkpoint window mismatch')
    return {'status':'PASS', 'evaluation_id':report['evaluation_id'], 'trials':len(records),
            'methods':len(report['methods']), 'files':len(entries), 'scope':'synthetic development diagnostic'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--verify', type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.output) if args.output else verify(args.verify), ensure_ascii=False))
