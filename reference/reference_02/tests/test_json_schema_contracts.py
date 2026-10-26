"""V0.6 JSON Schema contract smoke tests. pip install pytest jsonschema"""
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, ValidationError
BASE = Path(__file__).resolve().parents[1] / 'contracts'
EXAMPLES = json.loads((BASE/'examples.json').read_text(encoding='utf-8'))
@pytest.mark.parametrize('name', sorted(EXAMPLES))
def test_golden_example_valid(name):
    schema=json.loads((BASE/f'{name}.schema.json').read_text(encoding='utf8'))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(EXAMPLES[name])
@pytest.mark.parametrize('name', [n for n in EXAMPLES if n!='ApiError'])
def test_wrong_schema_version_rejected(name):
    data=dict(EXAMPLES[name],schema_version='999')
    schema=json.loads((BASE/f'{name}.schema.json').read_text(encoding='utf8'))
    with pytest.raises(ValidationError):Draft202012Validator(schema).validate(data)
def test_missing_device_id_rejected():
    data=dict(EXAMPLES['SensorObservation']);data.pop('device_id')
    schema=json.loads((BASE/'SensorObservation.schema.json').read_text(encoding='utf8'))
    with pytest.raises(ValidationError):Draft202012Validator(schema).validate(data)
def test_unknown_extra_field_rejected():
    data=dict(EXAMPLES['SafetyEvent']);data['status']='PENDING'
    schema=json.loads((BASE/'SafetyEvent.schema.json').read_text(encoding='utf8'))
    with pytest.raises(ValidationError):Draft202012Validator(schema).validate(data)
