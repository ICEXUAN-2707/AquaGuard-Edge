"""Read-only reference audit; writes evidence only, never changes contracts."""
from pathlib import Path
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/evidence'
OUT.mkdir(parents=True, exist_ok=True)

def save(name, value):
    (OUT / name).write_text(value, encoding='utf-8')

files = sorted((ROOT / 'reference').rglob('*'))
manifest = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files if p.is_file() and '__pycache__' not in p.parts]
save('reference_manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
for p in files:
    if p.suffix != '.docx':
        continue
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read('word/document.xml'))
        lines = ['SOURCE: ' + p.relative_to(ROOT).as_posix()]
        for para in root.findall('.//w:body//w:p', ns):
            value = ''.join(t.text or '' for t in para.findall('.//w:t', ns))
            if value:
                lines.append(value)
        save(p.stem + '.txt', '\n'.join(f'{i}: {s}' for i, s in enumerate(lines, 1)))

env = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
       'python': sys.version, 'platform': platform.platform(), 'sqlite': sqlite3.sqlite_version}
for name in ['pytest', 'jsonschema', 'pip']:
    env[name] = importlib.metadata.version(name)
save('environment.json', json.dumps(env, indent=2))
for name, cmd in [('pytest.log', [sys.executable, '-m', 'pytest', 'reference/reference_02/tests', '-q']),
                  ('pip_freeze.log', [sys.executable, '-m', 'pip', 'freeze']),
                  ('pip_check.log', [sys.executable, '-m', 'pip', 'check'])]:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    save(name, 'COMMAND: ' + ' '.join(cmd) + '\nEXIT: ' + str(result.returncode) + '\n' + result.stdout + result.stderr)
    print(name, 'exit', result.returncode, result.stdout.strip())

base = ROOT / 'reference/reference_02/contracts'
examples = json.loads((base / 'examples.json').read_text(encoding='utf-8'))
schemas = {p.stem.split('.')[0]: json.loads(p.read_text(encoding='utf-8')) for p in base.glob('*.schema.json')}
summary = {k: {'required': v.get('required'), 'properties': v['properties']} for k, v in schemas.items()}
save('schema_inventory.json', json.dumps(summary, ensure_ascii=False, indent=2))
probes = []
def probe(label, name, mutate):
    data = deepcopy(examples[name]); mutate(data)
    errors = list(Draft202012Validator(schemas[name]).iter_errors(data))
    probes.append({'probe': label, 'schema': name, 'accepted': not errors,
                   'errors': [e.message for e in errors], 'input': data})
probe('flow payload rejected', 'SensorObservation', lambda d: d.update(sensor_type='flow', value={'pulse_count': 10, 'interval_ms': 1000, 'estimated_lpm': 1.0, 'calibration_id': 'test'}))
probe('water payload rejected', 'SensorObservation', lambda d: d.update(sensor_type='water', value={'wet': True}))
probe('unknown presence null rejected', 'SensorObservation', lambda d: d['value'].update(present=None))
probe('unknown feature null rejected', 'FeatureWindow', lambda d: (d['features'].update(water_contact=None), d['missing_mask'].update(water=True)))
probe('invalid lifecycle accepted', 'SafetyEvent', lambda d: d.update(lifecycle='BANANA'))
probe('invalid source accepted', 'SensorObservation', lambda d: d.update(source='BANANA'))
probe('untrusted DEVICE_SYNCED accepted', 'SensorObservation', lambda d: d.update(time_basis='DEVICE_SYNCED', event_time=None))
probe('bad received_at accepted', 'SensorObservation', lambda d: d.update(received_at='yesterday'))
probe('invalid coverage accepted', 'FeatureWindow', lambda d: d['features'].update(data_coverage_ratio=2))
probe('negative attempts accepted', 'CloudSyncRecord', lambda d: d.update(attempts=-1))
probe('rule model score accepted', 'SituationAssessment', lambda d: d.update(model_score=0.99))
probe('flow summary rejected', 'AlignedWindow', lambda d: d['sensor_summary'].update(flow={'state': 'active', 'age_sec': 1, 'coverage_ratio': 1.0}))
probe('generic ApiError rejected', 'ApiError', lambda d: d.update(code='NOT_FOUND', details={}))
old = json.loads((ROOT / 'reference/reference_01/contracts_example.json').read_text(encoding='utf-8'))
for name, data in old.items():
    errors = list(Draft202012Validator(schemas[name]).iter_errors(data))
    probes.append({'probe': 'V0.5 example against V1.1 schema', 'schema': name, 'accepted': not errors, 'errors': [e.message for e in errors]})
save('contract_probes.json', json.dumps(probes, ensure_ascii=False, indent=2))
print('probes', len(probes), 'reference files', len(manifest))
