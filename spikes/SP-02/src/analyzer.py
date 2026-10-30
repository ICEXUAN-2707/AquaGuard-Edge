"""Compare sent measurement identities with accepted records."""
import argparse
import json
from collections import Counter
from pathlib import Path


def analyze(manifest, records):
    expected = {r['observation_id'] for r in manifest}
    accepted = [r['observation'] for r in records if r['classification'] in ('new', 'out_of_order')]
    actual = {r['observation_id'] for r in accepted}
    counts = Counter(r['classification'] for r in records)
    def canonical(row):
        return {k:v for k,v in row.items() if k != 'received_at'}
    by_id = {}
    content_conflicts = set()
    for row in manifest:
        identifier = row['observation_id']
        content = canonical(row)
        if identifier in by_id and by_id[identifier] != content:
            content_conflicts.add(identifier)
        by_id[identifier] = content
    mismatches = sorted(r['observation_id'] for r in accepted
                        if r['observation_id'] in by_id and canonical(r) != by_id[r['observation_id']])
    unknown = sorted(set(counts)-{'new','out_of_order','duplicate','invalid','conflict'})
    return dict(status='PASS' if expected and expected == actual and len(accepted) == len(actual) and not counts['invalid'] and not counts['conflict'] and not mismatches and not content_conflicts and not unknown else 'FAIL',
                sent_attempts=len(manifest), sent_unique=len(expected), received=len(records),
                accepted=len(accepted), classifications=dict(counts),
                missing=sorted(expected-actual), unexpected=sorted(actual-expected),
                content_mismatches=mismatches, manifest_conflicts=sorted(content_conflicts), unknown_classifications=unknown)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    def read(name):
        return [json.loads(s) for s in (args.directory/name).read_text(encoding='utf-8').splitlines() if s.strip()]
    result = analyze(read('manifest.jsonl'), read('received.jsonl'))
    (args.directory/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
