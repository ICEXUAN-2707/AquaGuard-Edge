"""Read-only evaluation queries and trusted local legacy B report import."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Literal
from pydantic import StrictInt, StrictBool, Field
from edge.contracts.models import DTO

from store import Store, NotFound, Conflict, canonical

METHODS={'B0_flow','B1_instant','B2_5s','B2_10s','B2_15s'}
COUNTS={'n','tp','fp','tn','fn','rejected_positive','rejected_negative'}


class EvaluationTrial(DTO):
    trial_id: str
    operation: str
    candidate_target: StrictBool
    parameters: dict
    predictions: dict[str, StrictBool | None]


class EvaluationMetrics(DTO):
    n: StrictInt
    tp: StrictInt
    fp: StrictInt
    tn: StrictInt
    fn: StrictInt
    rejected_positive: StrictInt
    rejected_negative: StrictInt
    rejection_rate: float = Field(ge=0,le=1,allow_inf_nan=False)
    positive_recall_all: float | None = Field(ge=0,le=1,allow_inf_nan=False)


class EvaluationReport(DTO):
    report_schema_version: Literal[1]
    evaluation_id: str
    source: Literal['simulation']
    task: Literal['binary_candidate']
    sample_unit: Literal['trial']
    trial_count: StrictInt
    class_counts: dict[str,StrictInt]
    split: dict
    records: list[EvaluationTrial]
    metrics: dict[str,EvaluationMetrics]
    metric_definitions: dict[str,str]
    provenance: dict
    unavailable: dict[str,str]
    limitations: list[str]


def load_legacy(path, root, evaluation_id):
    root=Path(root).resolve();path=Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('report outside approved root')
    if not evaluation_id or len(evaluation_id)>128:
        raise ValueError('invalid evaluation identity')
    if path.stat().st_size>2*1024*1024:
        raise ValueError('report too large')
    raw=path.read_bytes()
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('duplicate JSON field')
            result[key]=value
        return result
    def invalid(value): raise ValueError('nonfinite JSON number')
    data=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    json.dumps(data,allow_nan=False)  # Also reject exponent overflow in nested parameters.
    if set(data)!={'scope','records','metrics'} or data['scope']!='synthetic prototype_only; binary candidate task':
        raise ValueError('unsupported legacy report')
    records=data['records'];metrics=data['metrics']
    if not isinstance(records,list) or not 1<=len(records)<=1000 or set(metrics)!=METHODS:
        raise ValueError('invalid records or methods')
    ids=set()
    for row in records:
        if set(row)!={'trial_id','operation','candidate_target','parameters','predictions'}:
            raise ValueError('invalid record fields')
        if not isinstance(row['trial_id'],str) or not row['trial_id'] or row['trial_id'] in ids:
            raise ValueError('duplicate or empty trial')
        ids.add(row['trial_id'])
        if type(row['candidate_target']) is not bool or not isinstance(row['operation'],str) or not isinstance(row['parameters'],dict):
            raise ValueError('invalid label provenance')
        if set(row['predictions'])!=METHODS or any(value is not None and type(value) is not bool for value in row['predictions'].values()):
            raise ValueError('invalid predictions')
    positives=sum(row['candidate_target'] for row in records)
    for method,metric in metrics.items():
        if set(metric)!=COUNTS|{'rejection_rate','positive_recall_all'}:
            raise ValueError('invalid metrics')
        expected=dict.fromkeys(COUNTS,0);expected['n']=len(records)
        for row in records:
            target=row['candidate_target'];prediction=row['predictions'][method]
            key=('rejected_positive' if target else 'rejected_negative') if prediction is None else (
                'tp' if target and prediction else 'fn' if target else 'fp' if prediction else 'tn')
            expected[key]+=1
        if any(type(metric[k]) is not int or metric[k]!=expected[k] for k in COUNTS):
            raise ValueError('counts disagree with trial predictions')
        ratios=dict(rejection_rate=(expected['rejected_positive']+expected['rejected_negative'])/len(records),
                    positive_recall_all=None if not positives else expected['tp']/positives)
        for key,value in ratios.items():
            actual=metric[key]
            if value is None:
                if actual is not None: raise ValueError('undefined denominator')
            elif type(actual) not in (float,int) or not math.isfinite(actual) or not math.isclose(actual,value,abs_tol=1e-12):
                raise ValueError('ratio disagrees with denominator')
    value=dict(report_schema_version=1,evaluation_id=evaluation_id,source='simulation',
        task='binary_candidate',sample_unit='trial',trial_count=len(records),
        class_counts=dict(positive=positives,negative=len(records)-positives),
        split=dict(policy='scenario_set',training=False),records=records,metrics=metrics,
        metric_definitions=dict(rejection_rate='(rejected_positive + rejected_negative) / n',
            positive_recall_all='tp / all positive trials, including rejected positives',unit='fraction'),
        provenance=dict(adapter='b-r05-legacy-v1',artifact_sha256=hashlib.sha256(raw).hexdigest(),
            evaluation_code_commit=None,code_version_unavailable_reason='not recorded in legacy artifact',
            created_at=None,created_at_unavailable_reason='not recorded in legacy artifact'),
        unavailable=dict(latency='not measured',macro_f1='not computed by legacy binary evaluator',
            ml='not implemented',model_card='no ML model; rule report only'),
        limitations=['Historical synthetic scenario report is not real-world accuracy evidence.',
            'UNKNOWN is rejection, not a correct negative.',
            'Hidden present person and absent person can have identical observations.',
            'Legacy artifact has no full dataset hash, model provenance or train/test split.'])
    return EvaluationReport.model_validate(value).model_dump(mode='json')


class Evaluations(Store):
    def __init__(self,path):
        super().__init__(path)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS evaluations (evaluation_id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS experiment_evaluations (experiment_id TEXT NOT NULL,evaluation_id TEXT NOT NULL,relation_type TEXT NOT NULL,PRIMARY KEY(experiment_id,evaluation_id))')

    def register(self,report,experiment_id=None):
        identity=report['evaluation_id'];body=canonical(report)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT body FROM evaluations WHERE evaluation_id=?',(identity,)).fetchone()
            if old and old[0]!=body: raise Conflict('evaluation identity/content conflict')
            if experiment_id:
                trial=db.execute("SELECT body FROM query_projections WHERE kind='experiment' AND identity=?",(experiment_id,)).fetchone()
                if trial is None: raise NotFound(experiment_id)
                if json.loads(trial[0])['source']!='simulation': raise Conflict('cross-source association')
            db.execute('INSERT OR IGNORE INTO evaluations VALUES(?,?)',(identity,body))
            if experiment_id:
                db.execute('INSERT OR IGNORE INTO experiment_evaluations VALUES(?,?,?)',(experiment_id,identity,'reference'))

    def read(self,identity):
        with self.connection() as db:
            row=db.execute('SELECT body FROM evaluations WHERE evaluation_id=?',(identity,)).fetchone()
        if row is None: raise NotFound(identity)
        return json.loads(row[0])

    def associations(self,experiment_id):
        with self.connection() as db:
            rows=db.execute('SELECT evaluation_id,relation_type FROM experiment_evaluations WHERE experiment_id=? ORDER BY evaluation_id',(experiment_id,)).fetchall()
        return dict(report_schema_version=1,experiment_id=experiment_id,
            items=[dict(evaluation_id=row[0],relation_type=row[1],source='simulation') for row in rows])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--evaluation-id',required=True)
    parser.add_argument('--experiment-id')
    args=parser.parse_args()
    if not args.db.is_file(): parser.error('existing initialized business database required')
    report=load_legacy(args.report,args.root,args.evaluation_id)
    Evaluations(args.db).register(report,args.experiment_id)
    print(json.dumps(dict(evaluation_id=args.evaluation_id,status='IMPORTED',relation_type='reference' if args.experiment_id else None)))
