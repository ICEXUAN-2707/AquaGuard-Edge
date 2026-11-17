import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from mqtt_ack_summary import summarize


def record():
    return dict(scope='subscriber_commit_ack_submission',commit_returned=True,ack_submitted=True,broker_ack_confirmed=None,
                receive_to_commit_seconds=.1,commit_to_ack_submit_seconds=.2,receive_to_ack_submit_seconds=.3)


def test_valid_local_durations_do_not_become_cloud_or_business_latency(tmp_path):
    path=tmp_path/'timing.jsonl';path.write_text(json.dumps(record())+'\n')
    value=summarize(path)
    assert value['status']=='AVAILABLE' and value['completed']==1
    assert value['receive_to_ack_submit_seconds']['p95']==.3
    assert value['broker_confirmation']=='NOT_MEASURED' and not value['acceptance_passed']


def test_bad_or_partial_records_remain_in_denominator(tmp_path):
    path=tmp_path/'timing.jsonl'
    partial=record();partial['ack_submitted']=False
    invalid=record();invalid['receive_to_commit_seconds']=-1
    path.write_text('\n'.join([json.dumps(record()),json.dumps(partial),json.dumps(invalid),'not-json']))
    value=summarize(path)
    assert value['status']=='INCOMPLETE' and value['records']==4
    assert value['completed']==1 and value['incomplete']==1 and value['invalid']==2
    assert value['receive_to_ack_submit_seconds']['samples']==1


@pytest.mark.parametrize('change',['nan','inconsistent','broker_confirmation'])
def test_invalid_timing_or_receipt_claim_is_rejected(tmp_path,change):
    row=record()
    if change=='nan':row['receive_to_commit_seconds']=float('nan')
    if change=='inconsistent':row['receive_to_ack_submit_seconds']=2
    if change=='broker_confirmation':row['broker_ack_confirmed']=True
    path=tmp_path/'timing.jsonl';path.write_text(json.dumps(row)+'\n')
    assert summarize(path)['invalid']==1


def test_missing_file_is_unknown_and_not_created(tmp_path):
    path=tmp_path/'missing';value=summarize(path)
    assert value['status']=='INCOMPLETE' and value['records']==0
    assert not path.exists()
