"""Derive a versioned, duplicate-safe split proposal without relabeling truth."""
import argparse
import json
import hashlib
from pathlib import Path
from audit_b_sim_labels import audit


def repair(source, output):
    source, output = Path(source), Path(output)
    source = source.resolve()
    output = output.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError('output must be outside immutable source dataset')
    # audit refuses existing output, preventing accidental evidence overwrite.
    result = audit(source, output)
    trials = json.loads((source / 'trials.json').read_text(encoding='utf-8'))['trials']
    index = {t['trial_id']: t for t in trials}
    parents = {t['cohort_id']: t['cohort_id'] for t in trials}
    def root(group):
        while parents[group] != group:
            group = parents[group]
        return group
    for identities in result['exact_observation_duplicates']:
        groups = sorted({index[i]['cohort_id'] for i in identities})
        for group in groups[1:]:
            parents[root(group)] = root(groups[0])
    components = {}
    for group in sorted(parents):
        components.setdefault(root(group), []).append(group)
    # Deterministic subset search: retain target counts, minimize cohort moves.
    import itertools
    best = None
    groups = sorted(components.values())
    for choices in itertools.product(('train', 'validation', 'test'), repeat=len(groups)):
        assignment = {g: split for component, split in zip(groups, choices) for g in component}
        counts = {s: sum(assignment[t['cohort_id']] == s for t in trials) for s in choices}
        if any(counts.get(s, 0) != n for s, n in [('train', 36), ('validation', 18), ('test', 18)]):
            continue
        moved = sum(assignment[t['cohort_id']] != t['split'] for t in trials)
        candidate = (moved, choices, assignment)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ValueError('no duplicate-safe 36/18/18 split exists')
    assignment = best[2]
    for ids in result['exact_observation_duplicates']:
        assert len({assignment[index[i]['cohort_id']] for i in ids}) == 1
    parent_hash = hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest()
    proposal = {'schema': 'b-split-repair-v1', 'parent_manifest_sha256': parent_hash,
                'status': 'proposal-not-independent-test', 'training_ready': False,
                'reason': 'old test was already exposed; causal labels remain unresolved',
                'moved_trials': best[0], 'components': groups,
                'trials': {s: [t['trial_id'] for t in trials if assignment[t['cohort_id']] == s]
                           for s in ('train', 'validation', 'test')}}
    (output / 'repaired_split_proposal.json').write_text(json.dumps(proposal, indent=2) + '\n', encoding='utf-8')
    return proposal


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(repair(a.source, a.output), indent=2))
