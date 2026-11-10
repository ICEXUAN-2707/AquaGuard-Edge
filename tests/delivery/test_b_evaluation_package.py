"""Handoff invariants: reproducibility, accounting, portability and tamper rejection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/build_b_evaluation_package.py'
spec=importlib.util.spec_from_file_location('b_package_builder',SCRIPT)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope='module')
def package(tmp_path_factory):
    output=tmp_path_factory.mktemp('handoff')/'package'
    subprocess.run([sys.executable,str(SCRIPT),'--output',str(output)],cwd=ROOT,check=True,capture_output=True,text=True)
    return output


def load(package,name):
    return json.loads((package/name).read_text(encoding='utf-8'))


def rehash(package,name):
    manifest=load(package,'manifest.json')
    for item in manifest['files']:
        if item['path']==name:
            data=(package/name).read_bytes()
            item.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    (package/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')


def test_preserves_original_accounting_and_limits(package):
    assert builder.verify(package)['status']=='PASS'
    report=load(package,'evaluation.json')
    assert report['dataset']['trial_count']==8
    assert report['dataset']['positive_trials']==3
    assert report['dataset']['negative_trials']==5
    assert report['dataset']['split']['held_out_test'] is False
    assert report['acceptance']['g3_passed'] is False
    methods={r['method_id']:r for r in report['methods']}
    temporal=methods['B2_10s']
    assert temporal['counts']['fp']==1
    assert temporal['metrics']['positive_recall_all']==dict(value=2/3,unit='fraction',numerator=2,denominator=3)
    assert temporal['metrics']['rejection_rate']==dict(value=3/8,unit='fraction',numerator=3,denominator=8)
    assert report['unavailable_methods'][0]['availability']=='NOT_PROVIDED'
    assert all(r['value'] is None for r in report['unavailable_metrics'].values())


def test_indistinguishable_pair_and_trial_scoped_identity(package):
    rows=[json.loads(line) for line in (package/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
    trials=load(package,'trials.json')['trials']
    left=[r['observation'] for r in rows if r['trial_id']=='synthetic-left20']
    hidden=[r['observation'] for r in rows if r['trial_id']=='synthetic-hidden-person']
    assert left==hidden
    assert trials['synthetic-left20']['candidate_target'] is True
    assert trials['synthetic-hidden-person']['candidate_target'] is False
    assert len({(r['trial_id'],r['observation']['observation_id']) for r in rows})==len(rows)


def test_reproducible_values_in_another_directory(package,tmp_path):
    another=tmp_path/'another'
    subprocess.run([sys.executable,str(SCRIPT),'--output',str(another)],cwd=ROOT,check=True,capture_output=True,text=True)
    first,second=load(package,'evaluation.json'),load(another,'evaluation.json')
    assert first['evaluation_id']==second['evaluation_id']
    assert first['methods']==second['methods']
    assert (package/'predictions.jsonl').read_bytes()==(another/'predictions.jsonl').read_bytes()
    assert not str(package).encode() in (package/'predictions.jsonl').read_bytes()


def test_checksums_detect_corrupt_evidence(package,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(package,changed)
    with (changed/'observations.jsonl').open('a',encoding='utf-8') as file:file.write('{}\n')
    with pytest.raises(ValueError,match='digest mismatch'):builder.verify(changed)


def test_counts_cannot_be_changed_with_a_new_manifest_hash(package,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(package,changed)
    report=load(changed,'evaluation.json');report['methods'][0]['counts']['fp']=0
    (changed/'evaluation.json').write_text(json.dumps(report),encoding='utf-8');rehash(changed,'evaluation.json')
    with pytest.raises(ValueError,match='accounting mismatch'):builder.verify(changed)


def test_missing_predictions_detected_even_if_rehashed(package,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(package,changed)
    rows=(changed/'predictions.jsonl').read_text(encoding='utf-8').splitlines()
    (changed/'predictions.jsonl').write_text('\n'.join(rows[1:])+'\n',encoding='utf-8');rehash(changed,'predictions.jsonl')
    with pytest.raises(ValueError,match='prediction inventory'):builder.verify(changed)


def test_paths_cannot_escape_package(package,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(package,changed)
    manifest=load(changed,'manifest.json');manifest['files'][0]['path']='../outside.json'
    (changed/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError):builder.verify(changed)


def test_existing_package_never_overwritten(package):
    before=(package/'evaluation.json').read_bytes()
    result=subprocess.run([sys.executable,str(SCRIPT),'--output',str(package)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode!=0
    assert (package/'evaluation.json').read_bytes()==before
