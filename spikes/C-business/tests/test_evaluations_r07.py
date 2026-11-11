import copy
import hashlib
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'spikes/C-business'))
from evaluations import load_report,Evaluations
from projections import Projections
from test_api import create_app,http,TOKEN,NOW

SOURCE=ROOT/'spikes/SP-04/evidence/r07/report.json'


def test_r07_api_keeps_unknown_denominators_and_reference_relation(tmp_path):
    report=load_report(SOURCE,SOURCE.parent,'rules-r07')
    assert report['report_schema_version']==2 and report['trial_count']==34
    metric=report['report']['metrics']['C3_lightweight_ml_shadow']['eval']['metrics']
    assert (metric['n'],metric['decidable'],metric['unknown_required'])==(17,10,7)
    assert metric['correct_abstentions']==5
    assert report['provenance']['model_file_sha256']==hashlib.sha256((SOURCE.parent/'model/c3-model.json').read_bytes()).hexdigest()
    queries=Projections(tmp_path/'db')
    queries.publish('experiment',dict(schema_version='1.1',trial_id='mqtt-trial',source='simulation',status='RUNNING',started_at=NOW,ended_at=None,asset_refs=[]),captured_at=NOW)
    registry=Evaluations(queries.path);registry.register(report,'mqtt-trial');registry.register(report,'mqtt-trial')
    app=create_app(queries,token=TOKEN,cursor_key=b'x'*32,clock=lambda:NOW)
    status,value=http(app,'GET','/api/evaluations/rules-r07');assert status==200 and value==report
    assert http(app,'GET','/api/evaluations/rules-r07',auth=False)[0]==401
    assert http(app,'GET','/api/experiments/mqtt-trial/evaluations')[1]['items'][0]['relation_type']=='reference'
    with queries.connection() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM outbox').fetchone()[0]==0


@pytest.mark.parametrize('kind',['metric','split','shadow','prediction','modelhash','method','aggregation','structure'])
def test_r07_rejects_inconsistent_reports(tmp_path,kind):
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    data['model']['path']='model.json'
    (tmp_path/'model.json').write_bytes((SOURCE.parent/'model/c3-model.json').read_bytes())
    if kind=='metric':data['metrics']['C3_lightweight_ml_shadow']['eval']['metrics']['correct_abstentions']=7
    if kind=='split':data['dataset']['split']['eval'].append(data['dataset']['split']['train'][0])
    if kind=='shadow':data['trials'][0]['windows'][0]['methods']['C3_lightweight_ml_shadow']['shadow']=False
    if kind=='prediction':data['trials'][0]['methods']['C2_temporal_rules']['value']=1
    if kind=='modelhash':data['model']['sha256']='0'*64
    if kind=='method':del data['metrics']['C3_lightweight_ml_shadow']
    if kind=='aggregation':data['trials'][0]['methods']['C2_temporal_rules']['value']=True
    if kind=='structure':del data['trials']
    path=tmp_path/'report.json';path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError):load_report(path,tmp_path,'bad')
