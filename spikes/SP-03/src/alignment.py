"""Finite deterministic SP-03 experiment. No hardware or wall clock."""
from datetime import datetime, timedelta
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from edge.contracts.models import AlignedWindow, validate_raw_observation
ALGORITHM_VERSION = 'sp03-r05-v1'


def align(rows, ends, *, width=30, lateness=2, ttl=10, flow_threshold=0.1, ttl_by_source=None):
    if width <= 0 or ttl <= 0 or lateness < 0 or flow_threshold < 0:
        raise ValueError("invalid configuration")
    ttls = {s: ttl for s in ("flow", "water", "presence")}
    if ttl_by_source is not None:
        if set(ttl_by_source) != set(ttls) or any(v <= 0 for v in ttl_by_source.values()):
            raise ValueError("TTL configuration requires three positive values")
        ttls.update(ttl_by_source)
    observations = [validate_raw_observation(r) for r in rows]
    if len({r.device_id for r in observations}) > 1:
        raise ValueError("one device per experiment")
    unique = {}
    audit = []
    for r in sorted(observations, key=lambda r: (r.received_at, r.observation_id)):
        payload = r.model_dump(mode="json")
        key = (r.device_id, r.sensor_type, r.boot_id, r.seq)
        if r.observation_id in unique:
            if unique[r.observation_id].model_dump(mode="json") != payload:
                raise ValueError("conflicting observation identity")
            audit.append({"code": "DUPLICATE", "observation_id": r.observation_id})
            continue
        if any((v.device_id, v.sensor_type, v.boot_id, v.seq) == key for v in unique.values()):
            raise ValueError("conflicting sequence identity")
        unique[r.observation_id] = r
    observations = list(unique.values())
    device = observations[0].device_id if observations else "demo"
    config = dict(width=width, lateness=lateness, ttl=ttl, flow_threshold=flow_threshold, ttl_by_source=ttls)
    version = ALGORITHM_VERSION + "-" + hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    windows = []
    for end in sorted(set(ends)):
        if end.tzinfo is None:
            raise ValueError("window end needs timezone")
        start = end - timedelta(seconds=width)
        deadline = end + timedelta(seconds=lateness)
        summaries, refs, flags = {}, set(), set()
        for sensor in ("flow", "water", "presence"):
            candidates = []
            for r in observations:
                t = r.event_time or r.received_at
                if r.sensor_type != sensor or t > end:
                    continue
                if r.received_at > deadline:
                    if t > start:
                        audit.append(dict(code="LATE_FOR_WINDOW", observation_id=r.observation_id, window_end=end.isoformat()))
                    continue
                if t > r.received_at:
                    flags.add("FUTURE_EVENT_REJECTED")
                    continue
                candidates.append((t, r))
            candidates.sort(key=lambda pair: (pair[0], pair[1].boot_id, pair[1].seq, pair[1].observation_id))
            spans = []
            state, age = "unknown", None
            for i, (t, r) in enumerate(candidates):
                next_t = candidates[i+1][0] if i+1 < len(candidates) else end
                valid = r.quality == "valid"
                if sensor == "flow":
                    # Experimental assumption: event_time is the interval end.
                    a = t - timedelta(milliseconds=r.value.interval_ms)
                    b = t
                    value = "active" if r.value.estimated_lpm > flow_threshold else "inactive"
                else:
                    a, b = t, min(t + timedelta(seconds=ttls[sensor]), next_t, end)
                    value = ("wet" if r.value.wet else "dry") if sensor == "water" else ("present" if r.value.present else "absent")
                left, right = max(a, start), min(b, end)
                # Keep unknown/invalid interrupters in lineage as well as valid spans.
                if right > left or t == end or start < t <= end:
                    refs.add(r.observation_id)
                if valid and (right > left or t == end):
                    refs.add(r.observation_id)
                    if r.event_time is None:
                        flags.add("RECEIVED_FALLBACK")
                    if right > left:
                        spans.append((left, right))
                if sensor != "flow" and t <= end:
                    state, age = (value, (end-t).total_seconds()) if valid and end < t + timedelta(seconds=ttls[sensor]) else ("unknown", None)
                if sensor == "flow":
                    state, age = (value, 0.0) if valid and t == end else ("unknown", None)
            merged = []
            for a, b in sorted(spans):
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                else:
                    merged.append((a,b))
            coverage = sum((b-a).total_seconds() for a,b in merged) / width
            summaries[sensor] = dict(state=state, age_sec=age, coverage_ratio=coverage)
        sources = {r.source for r in observations if r.observation_id in refs}
        origin = "mixed" if len(sources)>1 else next(iter(sources)) if sources else "unknown"
        payload = dict(schema_version="1.1", window_id=f"{device}:{end.isoformat()}:{version}", device_id=device,
                       window_start=start.isoformat(), window_end=end.isoformat(), published_at=deadline.isoformat(),
                       alignment_config_version=version, sensor_summary=summaries, origin=origin,
                       quality_flags=sorted(flags), source_observation_ids=sorted(refs))
        windows.append(AlignedWindow.model_validate(payload).model_dump(mode="json"))
    return dict(config=config, windows=windows, audit=audit)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args=p.parse_args()
    data=json.loads(args.input.read_text(encoding="utf-8-sig"))
    result=align(data["observations"], [datetime.fromisoformat(t) for t in data["window_ends"]], **data["config"])
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"published {len(result['windows'])} windows")
