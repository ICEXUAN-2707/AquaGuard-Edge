import copy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'spikes/C-business'))
from evaluations import load_legacy, Evaluations
from projections import Projections
from store import Conflict
from test_api import create_app,http,TOKEN,NOW

SOURCE=ROOT/'spikes/SP-04/evidence/r05/comparison.json'


def report(): return load_legacy(SOURCE,SOURCE.parent,'rules-r05')


def test_report_preserves_rejection_denominators_and_unavailable_values():
    value=report()
    assert value['trial_count']==8
    assert value['metrics']['B2_10s']['fp']==1
    assert value['metrics']['B2_10s']['rejected_negative']==2
    assert value['provenance']['evaluation_code_commit'] is None
    assert value['unavailable']['latency']=='not measured'


def test_readonly_api_association_restart_and_auth(tmp_path):
    queries=Projections(tmp_path/'db')
    queries.publish('experiment',dict(schema_version='1.1',trial_id='mqtt-trial',source='simulation',
        status='RUNNING',started_at=NOW,ended_at=None,asset_refs=[]),captured_at=NOW)
    registry=Evaluations(queries.path)
    registry.register(report(),'mqtt-trial');registry.register(report(),'mqtt-trial')
    app=create_app(queries,token=TOKEN,cursor_key=b'x'*32,clock=lambda:NOW)
    assert http(app,'GET','/api/evaluations/rules-r05',auth=False)[0]==401
    status,value=http(app,'GET','/api/evaluations/rules-r05')
    assert status==200 and value==report()
    status,links=http(app,'GET','/api/experiments/mqtt-trial/evaluations')
    assert status==200 and links['items'][0]['relation_type']=='reference'
    assert http(app,'GET','/api/evaluations/missing')[0]==404
    assert http(app,'GET','/api/experiments/missing/evaluations')[0]==404
    assert Evaluations(queries.path).read('rules-r05')==report()
    changed=copy.deepcopy(report());changed['limitations'].append('different')
    with pytest.raises(Conflict): registry.register(changed)
    with queries.connection() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM outbox').fetchone()[0]==0


@pytest.mark.parametrize('kind',['count','nan','prediction','duplicate'])
def test_corrupt_reports_rejected(tmp_path,kind):
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    if kind=='count': data['metrics']['B0_flow']['fp']=0
    if kind=='nan': data['metrics']['B0_flow']['rejection_rate']=float('nan')
    if kind=='prediction': data['records'][0]['predictions']['B0_flow']=0
    if kind=='duplicate': data['records'][1]['trial_id']=data['records'][0]['trial_id']
    target=tmp_path/'bad.json';target.write_text(json.dumps(data))
    with pytest.raises(ValueError):load_legacy(target,tmp_path,'bad')


def test_outside_root_rejected(tmp_path):
    with pytest.raises(ValueError):load_legacy(SOURCE,tmp_path,'bad')
