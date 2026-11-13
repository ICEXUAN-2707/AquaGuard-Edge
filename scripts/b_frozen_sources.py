"""Explicit frozen dependency inventory for the B offline experiment."""
import hashlib
from pathlib import Path

REQUIRED_SOURCES = (
    'scripts/extract_b_expanded_features.py', 'scripts/b_feature_audit.py',
    'scripts/b_frozen_sources.py',
    *('scripts/'+name+'.py' for name in ('build_b_sim_dataset','b_training_inputs','b_bundle_checks','b_evidence_checks','train_b_proxy','publish_b_proxy_labels','evaluate_b_proxy','verify_b_proxy_fallback','verify_b_phase_delivery','compare_b_paired')),
    *('spikes/SP-03/src/'+n+'.py' for n in ('alignment','replay','stream')),
    *('spikes/SP-03-features/src/'+n+'.py' for n in ('basic_flow','checkpoint','continuous','engine','state_features','transitions')),
    *('spikes/SP-04/experiment/'+n+'.py' for n in ('__init__','config','generate','manifest','methods','metrics','ml','replay','report','run')),
    *('spikes/SP-04/src/'+n+'.py' for n in ('rules','gates','scenarios')),
    'spikes/SP-04/data/rules_config.json',
    *('edge/contracts/'+n+'.py' for n in ('__init__','api_models','models')),
)

def source_digests(root):
    root=Path(root).resolve();result={}
    for relative in REQUIRED_SOURCES:
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('required frozen dependency missing: '+relative)
        result[relative]=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    return result

def verify_sources(root, expected):
    if set(expected)!=set(REQUIRED_SOURCES):
        raise ValueError('frozen dependency inventory mismatch; missing='+repr(sorted(set(REQUIRED_SOURCES)-set(expected))))
    actual=source_digests(root)
    for relative,digest in expected.items():
        if actual[relative]!=digest:raise ValueError('frozen dependency changed: '+relative)
    return actual
