"""Content-addressed replay snapshots for the finite M4 experiment."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from engine import compute
from edge.contracts.models import FeatureWindow

FORMAT='m4-replay-checkpoint-v1'
FEATURE_VERSION='m4-r06-v1'

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')

def emit(result,reference):
    return FeatureWindow.model_validate(dict(schema_version='1.1',window_id=result['window_id'],device_id=result['device_id'],feature_version=result['feature_version'],features=result['features'],missing_mask=result['missing_mask'],origin=result['origin'],state_checkpoint_ref=reference)).model_dump(mode='json')

def save(directory,window,history,*,alignment_config):
    result=compute(window,history,alignment_config=alignment_config)
    payload=dict(format=FORMAT,feature_version=FEATURE_VERSION,window=window,history=sorted(history,key=lambda r:r['observation_id']),alignment_config=alignment_config,result=result)
    data=canonical(payload)
    digest=hashlib.sha256(data).hexdigest()
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(digest+'.json')
    # Validate all cross-field constraints before persisting anything.
    output=emit(result,str(target.resolve()))
    if target.exists():
        if target.read_bytes()!=data:raise ValueError('checkpoint content conflict')
    else:
        name=None
        try:
            with tempfile.NamedTemporaryFile(dir=directory,delete=False) as stream:
                name=stream.name;stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(name,target)
        finally:
            if name is not None and os.path.exists(name):os.unlink(name)
    return output

def restore(path,*,expected_config=None):
    path=Path(path)
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=path.stem:
        raise ValueError('checkpoint digest mismatch')
    payload=json.loads(data)
    if payload.get('format')!=FORMAT or payload.get('feature_version')!=FEATURE_VERSION:
        raise ValueError('checkpoint version mismatch')
    if expected_config is not None and canonical(payload['alignment_config'])!=canonical(expected_config):
        raise ValueError('checkpoint configuration mismatch')
    result=compute(payload['window'],payload['history'],alignment_config=payload['alignment_config'])
    if canonical(result)!=canonical(payload['result']):
        raise ValueError('checkpoint replay mismatch')
    return dict(history=payload['history'],alignment_config=payload['alignment_config'],last_window=payload['window'],feature_window=emit(result,str(path.resolve())))
