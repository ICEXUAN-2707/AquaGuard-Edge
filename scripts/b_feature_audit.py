"""P1 partition validation and metadata; never part of model input."""
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from b_frozen_sources import source_digests


def validate_split(split, trials):
    if set(split.get('trials', {})) != {'train','validation','test'}:
        raise ValueError('three named partitions required')
    assigned={}; cohorts={}
    expected={t['trial_id'] for t in trials}
    for partition, members in split['trials'].items():
        for identity in members:
            if identity in assigned or identity not in expected:
                raise ValueError('duplicate or unknown trial assignment')
            assigned[identity]=partition
    if set(assigned)!=expected:raise ValueError('incomplete split')
    for trial in trials:
        group=trial['cohort_id']; partition=assigned[trial['trial_id']]
        if cohorts.setdefault(group,partition)!=partition:raise ValueError('cohort split leakage')
    return assigned


def provenance(root, source, split_path):
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    files=[root/'scripts/extract_b_expanded_features.py',root/'scripts/b_feature_audit.py']
    for directory in ('spikes/SP-03/src','spikes/SP-03-features/src','spikes/SP-04/experiment','edge/contracts'):
        files.extend(sorted((root/directory).glob('*.py')))
    return dict(python=sys.version,packages={name:importlib.metadata.version(name) for name in ('pydantic','pydantic-core','annotated-types','typing-extensions','typing-inspection')},
                git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                source_files=source_digests(root),
                dataset_manifest_sha256=digest(source/'manifest.json'),split_sha256=digest(split_path),
                note='source hashes capture uncommitted implementation; commit alone is insufficient')


def diagnostics(records, trials):
    index={t['trial_id']:t for t in trials}; strata=defaultdict(list); vectors=defaultdict(list)
    for row in records:
        trial=index[row['trial_id']]
        strata[(row['split'],trial['scenario'])].append(row)
        vectors[json.dumps(row['features'],sort_keys=True,allow_nan=False)].append(row)
    collisions=[]
    for rows in vectors.values():
        if len({r['split'] for r in rows})<2:continue
        collisions.append(dict(windows=len(rows),scenarios=sorted({index[r['trial_id']]['scenario'] for r in rows}),
                               original_episode_targets=sorted({r['original_episode_target'] for r in rows}),
                               eligible_windows=sum(not r['rejection_reasons'] for r in rows),
                               interpretation='feature equality alone does not establish raw-data leakage'))
    return dict(strata=[dict(split=k[0],scenario=k[1],windows=len(rows),eligible=sum(not r['rejection_reasons'] for r in rows),
                             reasons=dict(Counter(reason for r in rows for reason in r['rejection_reasons']))) for k,rows in sorted(strata.items())],
                feature_collisions=collisions,near_duplicate_scope='not assessed; exact vector equality only')
