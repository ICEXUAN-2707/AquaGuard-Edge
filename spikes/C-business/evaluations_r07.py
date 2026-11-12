"""Versioned read-only R07 import. No training, inference or event writes."""
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal

from edge.contracts.models import DTO
from store import canonical

ROOT=Path(__file__).resolve().parents[2]
R07_METHODS={'C0_threshold_flow','C1_instant_multisource','C2_temporal_rules','C3_lightweight_ml_shadow'}


class R07EvaluationReport(DTO):
    report_schema_version: Literal[2]
    evaluation_id: str
    source: Literal['simulation']
    task: Literal['scenario_candidate_with_abstention']
    trial_count: int
    report: dict
    provenance: dict
    limitations: list[str]


def read_source(path,root):
    root=Path(root).resolve();path=Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size>4*1024*1024:
        raise ValueError('report outside approved root or too large')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON field')
            result[key]=value
        return result
    def invalid(value):raise ValueError('nonfinite JSON number')
    raw=path.read_bytes()
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    json.dumps(value,allow_nan=False)
    return path,root,raw,value


def load_r07(path,root,evaluation_id):
    path,root,raw,data=read_source(path,root)
    if not evaluation_id or len(evaluation_id)>128:raise ValueError('invalid evaluation identity')
    if data.get('report_version')!='b-exp-report-v1' or data.get('scope')!='synthetic_prototype_only':
        raise ValueError('unsupported R07 report')
    records=data['trials']
    if not isinstance(records,list) or not 1<=len(records)<=1000 or set(data['metrics'])!=R07_METHODS or set(data['method_definitions'])!=R07_METHODS:
        raise ValueError('invalid R07 trial/method inventory')
    ids=[]
    for record in records:
        identity=record['trial_id']
        if not isinstance(identity,str) or not identity or identity in ids or record['split'] not in ('train','eval'):
            raise ValueError('invalid or duplicate R07 trial')
        ids.append(identity)
        if record['expected'] not in ('candidate','no_candidate','unknown') or record['truth'] not in ('positive','negative','indistinguishable'):
            raise ValueError('invalid R07 target')
        if set(record['methods'])!=R07_METHODS:raise ValueError('missing R07 method')
        for method in record['methods'].values():
            if method['value'] is not None and type(method['value']) is not bool:raise ValueError('invalid R07 prediction')
        if record['decision_window_end_sec']!=data['dataset']['decision_window_end_sec']:
            raise ValueError('decision window mismatch')
        ends=[window['window_end_sec'] for window in record['windows']]
        if ends!=data['dataset']['window_ends_sec'] or len(ends)!=len(set(ends)):
            raise ValueError('window inventory mismatch')
        for window in record['windows']:
            if set(window['methods'])!=R07_METHODS:raise ValueError('window method inventory mismatch')
            for prediction in window['methods'].values():
                if prediction['value'] is not None and type(prediction['value']) is not bool:raise ValueError('invalid window prediction')
            if window['methods']['C3_lightweight_ml_shadow'].get('shadow') is not True:
                raise ValueError('C3 must remain shadow-only')
    split=data['dataset']['split']
    if set(split)!= {'train','eval'}:raise ValueError('invalid split names')
    flattened=split['train']+split['eval']
    if len(flattened)!=len(set(flattened)) or set(flattened)!=set(ids):raise ValueError('split overlap or missing trial')
    if any(record['trial_id'] not in split[record['split']] for record in records):raise ValueError('trial split mismatch')
    if data['manifest']['trials']!=len(records):raise ValueError('trial count mismatch')
    sys.path.insert(0,str(ROOT/'spikes/SP-04'))
    from experiment.metrics import methods_summary
    from experiment.methods import aggregate
    from experiment.ml import load_model
    for record in records:
        for method in R07_METHODS:
            expected=aggregate([window['methods'][method] for window in record['windows']],
                               [window['window_end_sec'] for window in record['windows']],record['decision_window_end_sec'])
            if canonical(expected)!=canonical(record['methods'][method]):raise ValueError('window aggregation mismatch')
    if canonical(methods_summary(records))!=canonical(data['metrics']):
        raise ValueError('R07 metrics or failure cases disagree with predictions')
    model_ref=Path(data['model']['path'])
    candidates=[(path.parent/model_ref).resolve(),(ROOT/model_ref).resolve()]
    model_path=next((candidate for candidate in candidates if candidate.is_relative_to(root) and candidate.is_file()),None)
    if model_path is None or model_path.stat().st_size>1024*1024:raise ValueError('model outside approved root or missing')
    model_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if model_hash!=data['model']['sha256']:raise ValueError('model file digest mismatch')
    model=load_model(model_path)
    if model['model_version']!=data['model']['model_version'] or canonical(model['training'])!=canonical(data['model']['training']):
        raise ValueError('model provenance mismatch')
    training=model['training']['trial_ids']
    if len(training)!=len(set(training)) or not set(training)<=set(split['train']):raise ValueError('model training split leakage')
    value=dict(report_schema_version=2,evaluation_id=evaluation_id,source='simulation',
               task='scenario_candidate_with_abstention',trial_count=len(records),report=data,
               provenance={'adapter':'b-r07-v1','artifact_sha256':hashlib.sha256(raw).hexdigest(),
                           'model_file_sha256':model_hash,'association_semantics':'reference'},
               limitations=['Historical frozen simulation report; not measurements of the currently running trial.',
                            'Decidable and unknown-required samples must be shown separately.',
                            'Logical window delay is not real network/hardware latency.'])
    return R07EvaluationReport.model_validate(value).model_dump(mode='json')
