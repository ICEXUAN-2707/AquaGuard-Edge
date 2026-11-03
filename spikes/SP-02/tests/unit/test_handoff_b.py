import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).parents[2]/'src'))
pytestmark = pytest.mark.skipif(not (Path(__file__).resolve().parents[4]/"spikes/SP-03/src/replay.py").exists() or not (Path(__file__).resolve().parents[4]/"spikes/SP-03-features/src/engine.py").exists(), reason="B implementation is a separate PR; A/B integration is not claimed in A-only gate")

from core import normalize,sample
from handoff_b import handoff


def row(seq,sensor='water',boot='b1'):
    return normalize(json.dumps(sample(seq,sensor,boot)),'prototype01','simulation',
                     received_at=f'2026-10-30T00:00:{seq:02d}+00:00')


def test_three_sources_keep_simulation_and_fallback():
    result = handoff([row(1,'flow'),row(1,'water'),row(1,'presence')])
    experiment = result['experiments'][0]
    assert experiment['window']['origin']=='simulation'
    assert 'RECEIVED_FALLBACK' in experiment['window']['quality_flags']
    assert experiment['features']['origin']=='simulation'


def test_reboots_are_separate_experiments():
    result = handoff([row(1),row(1,boot='b2')])
    assert len(result['experiments'])==2
    assert result['experiments'][0]['experiment_id'] != result['experiments'][1]['experiment_id']


def test_overlapping_flow_is_reported_not_silently_changed():
    first = row(1,'flow')
    second = row(2,'flow')
    second['received_at']='2026-10-30T00:00:01.100000+00:00'
    result = handoff([first,second])
    assert result['status']=='PARTIAL'
    assert 'overlapping' in result['experiments'][0]['reason']


def test_duplicate_export_rejected():
    original = row(1)
    with pytest.raises(ValueError):
        handoff([original,original])


def test_sequence_identity_conflict_has_structured_reason():
    first = row(1)
    second = dict(first,observation_id='different-id')
    result = handoff([first,second])
    assert result['status']=='PARTIAL'
    assert result['experiments'][0]['window'] is None
    assert 'sequence identity' in result['experiments'][0]['reason']


def test_empty_handoff_not_pass():
    assert handoff([])['status']=='PARTIAL'


def test_multidevice_isolation():
    first = row(1)
    second = dict(first,device_id='other',observation_id='other-id')
    result = handoff([second,first])
    assert result['status']=='PASS'
    assert {r['window']['device_id'] for r in result['experiments']} == {'other','prototype01'}
