import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('mqtt_plan',Path(__file__).resolve().parents[2]/'scripts/prepare_mqtt_protocol.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.mark.parametrize('overrides',[
    {'stop_seconds':10},{'ttl':float('nan')},{'interval':False},
    {'revision':'main'},{'continuous_seconds':1,'interval':15},
])
def test_invalid_plan_leaves_no_output(tmp_path,overrides):
    config=dict(revision='a'*40,ttl=10,stop_seconds=18);config.update(overrides)
    with pytest.raises(ValueError):module.prepare(tmp_path/'plan',**config)
    assert not (tmp_path/'plan').exists()


def test_preparation_does_not_execute_and_preserves_boot_recovery_contract(tmp_path):
    value=module.prepare(tmp_path/'plan',revision='a'*40,ttl=10,stop_seconds=18)
    stages={stage['name']:stage for stage in value['stages']}
    assert value['status']=='PREPARED' and not value['execution_enabled'] and not value['acceptance_passed']
    assert stages['continuous']['boot']==stages['resume_duplicate']['boot']==stages['edge_restart']['boot']
    assert stages['new_boot']['boot']!=stages['continuous']['boot']
    assert json.loads((tmp_path/'plan/plan.json').read_text())==value
    original=(tmp_path/'plan/plan.json').read_bytes()
    with pytest.raises(FileExistsError):module.prepare(tmp_path/'plan',revision='b'*40,ttl=10,stop_seconds=18)
    assert (tmp_path/'plan/plan.json').read_bytes()==original
