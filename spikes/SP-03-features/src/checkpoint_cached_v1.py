"""Opt-in content cache v1; never replaces frozen checkpoint.restore.

Use only with explicitly selected callers. Existing B/C pipelines do not import
this module, so their independent replay counts and provenance remain unchanged.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
from pathlib import Path
import checkpoint

CACHE_VERSION='m4-verified-content-cache-v1'
_cache=ContextVar('m4_verified_cache_v1',default=None)

@contextmanager
def verification_scope():
    token=_cache.set({})
    try:yield
    finally:_cache.reset(token)

def restore(path,*,expected_config=None):
    path=Path(path);data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=path.stem:raise ValueError('checkpoint digest mismatch')
    cache=_cache.get()
    value=cache.get(data) if cache is not None else None
    if value is None:
        value=checkpoint.restore(path,expected_config=expected_config)
        if cache is not None and len(cache)<4:cache[data]=deepcopy(value)
    elif expected_config is not None and checkpoint.canonical(value['alignment_config'])!=checkpoint.canonical(expected_config):
        raise ValueError('checkpoint configuration mismatch')
    output=deepcopy(value)
    output['feature_window']['state_checkpoint_ref']=str(path.resolve())
    return output
