"""Round 01: deterministic observation replay, not a window engine."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from edge.contracts.models import validate_raw_observation


def replay(rows):
    validated = [validate_raw_observation(row) for row in rows]
    identities = [r.observation_id for r in validated]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate observation_id; deduplication belongs to round 02")
    ordered = sorted(validated, key=lambda r: (r.received_at, r.observation_id))
    return [dict(virtual_time=r.received_at.isoformat(),
                 effective_time=(r.event_time or r.received_at).isoformat(),
                 degraded_time=r.event_time is None,
                 observation=r.model_dump(mode="json")) for r in ordered]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    result = replay(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in result), encoding="utf-8")
    print(f"replayed {len(result)} observations; no wall-clock waiting")


if __name__ == "__main__":
    main()
