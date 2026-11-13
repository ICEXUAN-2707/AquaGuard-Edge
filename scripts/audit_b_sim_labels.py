"""Read-only B-SIM label and split audit. Never trains or rewrites source data."""
import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from build_b_sim_dataset import verify


def audit(source, output):
    source, output = Path(source), Path(output)
    verification = verify(source)
    trials = json.loads((source / 'trials.json').read_text(encoding='utf-8'))['trials']
    index = {t['trial_id']: t for t in trials}
    labels = [json.loads(s) for s in (source / 'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    # Exclude only trial-scoped identity; preserve timestamps, values and quality.
    streams = defaultdict(list)
    for line in gzip.decompress((source / 'observations.jsonl.gz').read_bytes()).splitlines():
        item = json.loads(line)
        row = {k: v for k, v in item['observation'].items()
               if k not in ('observation_id', 'device_id', 'boot_id')}
        streams[item['trial_id']].append(row)
    fingerprints = defaultdict(list)
    for identity, rows in streams.items():
        canonical = json.dumps(sorted(rows, key=lambda r: (r['sensor_type'], r['seq'])), sort_keys=True)
        fingerprints[hashlib.sha256(canonical.encode()).hexdigest()].append(identity)
    duplicates = [ids for ids in fingerprints.values() if len(ids) > 1]
    cross_split = [ids for ids in duplicates if len({index[i]['split'] for i in ids}) > 1]
    result = {'verification': verification, 'exact_observation_duplicates': duplicates,
              'cross_split_duplicates': cross_split,
              'training_ready': False,
              'blockers': ['episode labels are not causal candidate labels',
                           'candidate task and quality rejection contract must be versioned']}
    if cross_split:
        result['blockers'].append('identical observations cross partitions')
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'label_audit.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['trial_id', 'window_end', 'split', 'scenario', 'original_target', 'issue', 'disposition'])
        for label in labels:
            trial = index[label['trial_id']]
            scenario = trial['scenario']
            issue = {'brief_leave': 'episode negative uses future return',
                     'hidden_present': 'observationally identical to unattended',
                     'unattended': 'observationally identical to hidden_present',
                     'presence_dropout': 'absence of messages is not evidence of absence'}.get(scenario, 'review causal window evidence')
            writer.writerow([trial['trial_id'], label['window_end'], trial['split'], scenario,
                             label['candidate_target'], issue, 'preserve original; do not train as causal truth'])
    (output / 'split_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.source, args.output), ensure_ascii=False))
