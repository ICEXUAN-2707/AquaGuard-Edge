"""Strict source and cohort checks before any proxy model fitting."""
import hashlib
import json
from pathlib import Path
from b_feature_audit import validate_split
from build_b_sim_dataset import verify
from b_frozen_sources import verify_sources

def verify_inputs(root,feature_manifest,plan,rows,source=None,split=None):
    root=Path(root)
    source=Path(source) if source else root/'deliverables/B-SIM-001'
    split=Path(split) if split else root/'deliverables/B-PROXY-INPUTS-001/repaired_split_proposal.json'
    verify(source)
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    if sha(split)!=plan['split_sha256']:raise ValueError('split digest mismatch')
    if sha(source/'manifest.json')!=feature_manifest['provenance']['dataset_manifest_sha256']:raise ValueError('dataset manifest mismatch')
    assignments=validate_split(json.loads(split.read_text()),json.loads((source/'trials.json').read_text())['trials'])
    if {r['trial_id'] for r in rows}!=set(assignments):raise ValueError('trial inventory mismatch')
    for row in rows:
        if row['split']!=assignments[row['trial_id']]:raise ValueError('row differs from frozen split')
    verify_sources(root,feature_manifest['provenance']['source_files'])
    return {'source_manifest_sha256':sha(source/'manifest.json'),'split_sha256':sha(split),'cohort_validation':'PASS'}
