import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_mqtt_protocol import prepare
from mqtt_protocol_runner import execute


class Backend:
    def __init__(self,fail=None):self.fail=fail;self.calls=[]
    def preflight(self,plan):self.calls.append('preflight')
    def start(self,output,plan):
        self.calls.append('start')
        if self.fail=='ready':raise TimeoutError('READY not reached')
    def enter(self,stage):
        self.calls.append(stage['name'])
        return {'ready':self.fail!='missing_ready','checks':['test_only']}
    def ensure_alive(self,stage):
        if self.fail=='dead':raise RuntimeError('early child exit')
    def observe(self,stage):return {'live':{'status':503 if stage['name']=='publisher_stop' else 200}}
    def assert_phase(self,stage,samples):return {'status':'VIOLATED' if self.fail=='assertion' else 'INCOMPLETE' if self.fail=='evidence' else 'SATISFIED','checks':[]}
    def stop(self):self.calls.append('stop');return {'all_exited':self.fail!='cleanup'}
    def exit_checks(self):self.calls.append('exit_checks');return {'ok':self.fail!='integrity'}


def plan(tmp_path):return prepare(tmp_path/'plan',revision='a'*40,ttl=10,stop_seconds=18,continuous_seconds=30,interval=15)


def run(tmp_path,backend):
    ticks=[0.0]
    def sleep(seconds):ticks[0]+=seconds
    return execute(plan(tmp_path),backend,tmp_path/'run',allow_execution=True,allow_long_run=True,clock=lambda:ticks[0],sleep=sleep)


@pytest.mark.parametrize('flags',[{}, {'allow_execution':True}])
def test_execution_and_long_run_gates_are_before_any_backend_activity(tmp_path,flags):
    backend=Backend()
    with pytest.raises(ValueError):execute(plan(tmp_path),backend,tmp_path/'run',**flags)
    assert backend.calls==[] and not (tmp_path/'run').exists()


def test_fake_phases_are_recorded_without_promoting_fault_503_to_pass(tmp_path):
    backend=Backend();result=run(tmp_path,backend)
    assert result['execution_status']=='COMPLETED' and not result['acceptance_passed'] and not result['long_run_acceptance']
    phases=[json.loads(line) for line in (tmp_path/'run/phases.jsonl').read_text().splitlines()]
    assert [row['state'] for row in phases if row['state'] not in ('READY','ASSERTED')]==['ENTERED','FINISHED']*7
    assert [row['phase'] for row in phases if row['state']=='READY']==['startup','edge_restart']
    assert all(row['assertions_status']=='SATISFIED' for row in phases if row['state']=='FINISHED')
    samples=[json.loads(line) for line in (tmp_path/'run/samples.jsonl').read_text().splitlines()]
    assert any(row['phase']=='publisher_stop' and row['live']['status']==503 for row in samples)
    assert backend.calls[-2:]==['stop','exit_checks']


@pytest.mark.parametrize('failure',['ready','missing_ready','dead','cleanup','integrity','assertion','evidence'])
def test_failures_retain_receipts_and_run_owned_cleanup(tmp_path,failure):
    backend=Backend(failure);result=run(tmp_path,backend)
    assert result['execution_status']=='FAILED' and not result['acceptance_passed']
    assert 'stop' in backend.calls
    assert json.loads((tmp_path/'run/result.json').read_text())==result
    if failure=='ready':
        assert result['error_type']=='TimeoutError' and not result['completed_phases']
    if failure=='cleanup':
        assert 'exit_checks' not in backend.calls
        assert result['exit_checks']['status']=='SKIPPED_UNCONFIRMED_PROCESS_EXIT'


def test_invalid_boot_contract_is_rejected_before_output(tmp_path):
    value=plan(tmp_path);value['stages'][5]['boot']=value['stages'][0]['boot']
    with pytest.raises(ValueError):execute(value,Backend(),tmp_path/'run',allow_execution=True,allow_long_run=True)
    assert not (tmp_path/'run').exists()
