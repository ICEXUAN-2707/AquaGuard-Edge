"""Finite prototype handoff: canonical A export into isolated B boot experiments."""
import argparse
import json
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'spikes/SP-03/src'))
sys.path.insert(0,str(ROOT/'spikes/SP-03-features/src'))
from edge.contracts.models import validate_raw_observation


def handoff(rows):
    try:
        from replay import replay
        from alignment import align
        from engine import compute
    except ModuleNotFoundError as exc:
        raise ValueError("B validation modules are not installed; merge the B-line PR before running A/B handoff") from exc
    # Replay is the common boundary: full DTO and unique observation identities.
    ordered = [r['observation'] for r in replay(rows)]
    groups = {}
    for row in ordered:
        key = (row['device_id'], row['boot_id'])
        groups.setdefault(key, []).append(row)
    results = []
    for (device,boot), history in groups.items():
        parsed = [validate_raw_observation(r) for r in history]
        end = max(r.received_at for r in parsed)
        config = dict(width=30,lateness=2,ttl=10,flow_threshold=0.1)
        experiment_id = hashlib.sha256(json.dumps([device,boot]).encode()).hexdigest()
        result = dict(experiment_id=experiment_id,device_id=device,boot_id=boot,window=None)
        try:
            packet = align(history,[end],**config)
            window = packet['windows'][0]
            result['window'] = window
            result.update(features=compute(window,history,alignment_config=config),status='PASS')
        except ValueError as exc:
            result.update(features=None,status='BLOCKED',reason=str(exc))
        results.append(result)
    return dict(status='PASS' if results and all(r['status']=='PASS' for r in results) else 'PARTIAL',
                prototype_only=True,observations=len(ordered),experiments=results,
                limitations=['Each device/boot is an independent finite experiment; not a continuous restart timeline.',
                             'RECEIVED_FALLBACK cannot reconstruct measurement time of queued messages.',
                             'M4 output is experimental features, not a checkpoint-backed FeatureWindow.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    rows = []
    try:
        rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        result = handoff(rows)
    except (ValueError,TypeError,KeyError) as exc:
        result = dict(status='FAIL',prototype_only=True,observations=len(rows),experiments=[],reason=str(exc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(f"handed off {len(rows)} observations across {len(result['experiments'])} isolated experiments")
    raise SystemExit(0 if result['status']=='PASS' else 1)


if __name__=='__main__':
    main()
