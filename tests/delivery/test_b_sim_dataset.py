import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/build_b_sim_dataset.py'
spec=importlib.util.spec_from_file_location('b_sim_builder',SCRIPT)
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


@pytest.fixture(scope='module')
def dataset(tmp_path_factory):
    output=tmp_path_factory.mktemp('b-sim')/'dataset'
    subprocess.run([sys.executable,str(SCRIPT),'--output',str(output)],cwd=ROOT,check=True,capture_output=True,text=True)
    return output


def read(dataset,name):return json.loads((dataset/name).read_text(encoding='utf-8'))


def test_declared_trial_split_has_no_group_or_window_overlap(dataset):
    assert builder.verify(dataset)['status']=='PASS'
    meta=read(dataset,'dataset.json');split=read(dataset,'split_manifest.json')
    assert meta['trial_count']==72 and meta['window_label_count']==216
    assert meta['split_trial_counts']=={'train':36,'validation':18,'test':18}
    groups=[identity for items in split['groups'].values() for identity in items]
    assert len(groups)==len(set(groups))==12
    assert not meta['training_complete'] and not meta['evaluation_complete']


def test_repeated_generation_is_byte_identical(dataset,tmp_path):
    another=tmp_path/'another'
    subprocess.run([sys.executable,str(SCRIPT),'--output',str(another)],cwd=ROOT,check=True,capture_output=True,text=True)
    for name in ['observations.jsonl.gz','labels.jsonl','trials.json','split_manifest.json','dataset.json']:
        assert (dataset/name).read_bytes()==(another/name).read_bytes()


def test_ambiguous_pairs_have_same_sensor_values_and_same_partition(dataset):
    trials=read(dataset,'trials.json')['trials']
    data=[json.loads(line) for line in gzip.decompress((dataset/'observations.jsonl.gz').read_bytes()).splitlines()]
    def signature(trial_id):
        return [{key:row['observation'][key] for key in ['sensor_type','event_time','received_at','value','quality']} for row in data if row['trial_id']==trial_id]
    for group in {trial['cohort_id'] for trial in trials}:
        paired={trial['scenario']:trial for trial in trials if trial['cohort_id']==group}
        absent,present=paired['unattended'],paired['hidden_present']
        assert absent['split']==present['split']
        assert absent['candidate_target'] is True and present['candidate_target'] is False
        assert signature(absent['trial_id'])==signature(present['trial_id'])


def test_corrupt_compressed_input_is_rejected(dataset,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(dataset,changed)
    (changed/'observations.jsonl.gz').write_bytes(b'corrupt')
    with pytest.raises(ValueError):builder.verify(changed)


def test_rehashed_split_cannot_move_one_window_to_another_partition(dataset,tmp_path):
    changed=tmp_path/'changed';shutil.copytree(dataset,changed)
    labels=[json.loads(line) for line in (changed/'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    labels[0]['split']='test' if labels[0]['split']!='test' else 'train'
    label_bytes=b''.join(builder.packed(row)+b'\n' for row in labels)
    (changed/'labels.jsonl').write_bytes(label_bytes)
    meta=read(changed,'dataset.json')
    meta['label_sha256']=builder.sha(label_bytes)
    trials=read(changed,'trials.json')['trials']
    meta['dataset_sha256']=builder.sha(builder.packed({'trials':trials,'labels':labels,'observations_sha256':meta['observations_uncompressed_sha256']}))
    meta['dataset_id']='b-sim1-'+meta['dataset_sha256'][:16]
    builder.json_file(changed/'dataset.json',meta)
    split=read(changed,'split_manifest.json');split['dataset_id']=meta['dataset_id'];builder.json_file(changed/'split_manifest.json',split)
    manifest=read(changed,'manifest.json')
    for item in manifest['files']:
        content=(changed/item['path']).read_bytes();item.update(bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
    builder.json_file(changed/'manifest.json',manifest)
    with pytest.raises(ValueError,match='window label'):builder.verify(changed)


def test_changed_seed_changes_dataset_identity(tmp_path):
    result=builder.build(tmp_path/'other',seed=7,cohorts=6)
    assert result['trials']==36
    assert result['dataset_id']!='b-sim1-65ff0bbbac70fcc2'


def test_existing_dataset_is_not_overwritten(dataset):
    with pytest.raises(FileExistsError):builder.build(dataset)


def test_training_validation_samples_enter_native_b_pipeline(dataset,tmp_path):
    from datetime import datetime,timedelta
    sys.path.insert(0,str(ROOT/'spikes/SP-04'))
    import evaluate  # Establish the existing B engine import paths.
    from alignment import align
    from checkpoint import save,restore
    from rules import classify
    trials=read(dataset,'trials.json')['trials']
    data=[json.loads(line) for line in gzip.decompress((dataset/'observations.jsonl.gz').read_bytes()).splitlines()]
    selected={}
    for trial in trials:
        if trial['split']!='test':selected.setdefault((trial['scenario'],trial['parameters']['cadence_sec']),trial)
    for trial in selected.values():
        rows=[item['observation'] for item in data if item['trial_id']==trial['trial_id']]
        for second in builder.ENDS:
            end=builder.START+timedelta(seconds=second)
            window=align(rows,[end])['windows'][0]
            feature=save(tmp_path/'checkpoints',window,rows,alignment_config={})
            assert len(feature['features'])==12
            assert restore(feature['state_checkpoint_ref'])['feature_window']==feature
            result=classify(feature,end+timedelta(seconds=2),checkpoint_root=tmp_path)
            assert result['situation'] in ('IDLE','ATTENDED_FLOW','POSSIBLE_UNATTENDED_FLOW','UNKNOWN')
            assert result['origin']=='simulation'
