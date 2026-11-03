import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('sp02core', Path(__file__).parents[2] / 'src/core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def normalized(row):
    return core.normalize(json.dumps(row), 'prototype01', 'simulation')


@pytest.mark.parametrize('sensor', ['flow', 'water', 'presence'])
def test_three_sources(sensor):
    assert normalized(core.sample(sensor=sensor))['sensor_type'] == sensor


def test_restart_order_conflict_and_export(tmp_path):
    path = tmp_path / 'journal.sqlite'
    journal = core.Journal(path)
    assert journal.accept(normalized(core.sample(3))) == 'new'
    assert journal.accept(normalized(core.sample(2))) == 'out_of_order'
    journal.close()
    journal = core.Journal(path)
    assert journal.accept(normalized(core.sample(3))) == 'duplicate'
    changed = core.sample(3)
    changed['value']['wet'] = True
    assert journal.accept(normalized(changed)) == 'conflict'
    assert journal.accept(normalized(core.sample(0, boot='boot-2'))) == 'new'
    assert len(journal.export()) == 3
    journal.close()


@pytest.mark.parametrize('change', [ {'received_at': '2026-01-01T00:00:00Z'}, {'source': 'hardware'},
    {'schema_version': '1.0'}, {'quality': 'duplicate'}, {'event_time': '2026-01-01T00:00:00Z'},
    {'observation_id': 'forged'}, {'prototype_only': True}])
def test_reject(change):
    row = core.sample()
    row.update(change)
    with pytest.raises(ValueError):
        normalized(row)


def test_unknown():
    row = core.sample()
    row.update(value={'wet': None}, quality='unknown')
    assert normalized(row)['value']['wet'] is None
