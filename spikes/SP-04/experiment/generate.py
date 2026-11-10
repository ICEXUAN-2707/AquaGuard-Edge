"""Deterministic synthetic observation generator for the frozen B trials.

The generator renders declared operation timelines into DTO-shaped raw
observations. It never imports a rule, feature or model module, so the label of
a trial can only come from the manifest's authored operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from experiment.manifest import expand_trials, load_manifest

MASK64 = (1 << 64) - 1


class DeterministicRng:
    """xorshift64* so a frozen seed is reproducible without library RNG drift."""

    def __init__(self, seed: int) -> None:
        state = (seed * 6364136223846793005 + 1442695040888963407) & MASK64
        self.state = state or 1

    def u64(self) -> int:
        value = self.state
        value ^= value >> 12
        value ^= (value << 25) & MASK64
        value ^= value >> 27
        self.state = value & MASK64
        return (value * 2685821657736338717) & MASK64

    def below(self, bound: int) -> int:
        return self.u64() % bound

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * (self.u64() / float(1 << 64))


@dataclass(frozen=True)
class TrialData:
    trial_id: str
    scenario_id: str
    title: str
    split: str
    seed: int
    truth: str
    expected: str
    onset_sec: float | None
    anomaly: str
    notes: str
    rows: list[dict] = field(repr=False)
    window_ends: list[datetime] = field(repr=False)
    window_ends_sec: list[int]
    decision_end_sec: int


def _value_at(segments: list[dict], key: str, instant: float) -> object:
    if instant == segments[-1]["to"]:
        # A sample exactly on the stream end carries the value just before it.
        return segments[-1][key]
    for segment in segments:
        if segment["from"] <= instant < segment["to"]:
            return segment[key]
    raise ValueError(f"operation does not cover t={instant}")


def _sample_times(sensor: str, anomaly: str, duration: int, period: int = 5) -> list[int]:
    times = list(range(0, duration + 1, period))
    if sensor == "flow":
        times = [t for t in times if t > 0]
    if sensor == "presence" and anomaly == "slow_presence":
        times = [t for t in times if t <= 20] + list(range(35, duration + 1, 15))
    if sensor == "presence" and anomaly == "presence_stop":
        times = [t for t in times if t <= 15]
    if sensor == "flow" and anomaly == "flow_stop":
        times = [t for t in times if t <= 20]
    return sorted(set(times))


def _delay_ms(anomaly: str, sensor: str, t: int, rng: DeterministicRng) -> int:
    if anomaly == "async_sources":
        base = {"flow": 300, "water": 900, "presence": 1400}[sensor]
        return base + rng.below(501)
    if anomaly == "late_presence" and sensor == "presence" and t >= 30:
        return 8000
    return 0


def _boot_id(anomaly: str, t: int) -> str:
    if anomaly == "restart" and t >= 25:
        return "b"
    return "a"


def generate_trial(trial: dict, scenario: dict, manifest: dict) -> TrialData:
    origin = datetime.fromisoformat(manifest["time_origin"]) + timedelta(seconds=trial["offset_sec"])
    duration = manifest["stream_duration_sec"]
    anomaly = scenario["anomaly"]
    rng = DeterministicRng(trial["seed"] ^ (sum(map(ord, scenario["scenario_id"])) << 8))
    rows: list[dict] = []
    boot_counters: dict[tuple[str, str], int] = {}

    for sensor in ("flow", "water", "presence"):
        for t in _sample_times(sensor, anomaly, duration):
            boot = _boot_id(anomaly, t)
            uptime = (t - 25) * 1000 if boot == "b" else t * 1000
            seq = boot_counters.get((sensor, boot), 0)
            boot_counters[(sensor, boot)] = seq + 1
            event = origin + timedelta(seconds=t)
            received = event + timedelta(milliseconds=_delay_ms(anomaly, sensor, t, rng))
            quality = "valid"
            if sensor == "flow":
                value = {
                    "pulse_count": 1 if _value_at(scenario["operation"]["flow"], "lpm", t) > 0 else 0,
                    "interval_ms": 5000,
                    "estimated_lpm": float(_value_at(scenario["operation"]["flow"], "lpm", t)),
                    "calibration_id": "synthetic",
                }
            elif sensor == "water":
                value = {"wet": bool(_value_at(scenario["operation"]["water"], "wet", t))}
            else:
                present = bool(_value_at(scenario["operation"]["presence"], "present", t))
                if anomaly == "presence_miss":
                    present = False
                moving = bool(present and scenario["presence_motion"] == "moving")
                still = bool(present and not moving)
                value = {"present": present, "moving": moving, "still": still}
                if anomaly == "invalid_presence" and t >= 20:
                    quality = "invalid"
            rows.append(
                {
                    "schema_version": "1.1",
                    "observation_id": f"{trial['trial_id']}:{sensor}:{boot}:{seq}",
                    "device_id": manifest["device_id"],
                    "sensor_type": sensor,
                    "boot_id": boot,
                    "seq": seq,
                    "uptime_ms": uptime,
                    "event_time": event.isoformat(),
                    "received_at": received.isoformat(),
                    "time_basis": "DEVICE_SYNCED",
                    "value": value,
                    "quality": quality,
                    "source": "simulation",
                }
            )

    if anomaly == "duplicates":
        duplicated = [dict(row) for index, row in enumerate(rows) if index % 4 == 1]
        rows.extend(duplicated)

    rows.sort(key=lambda row: (row["received_at"], row["observation_id"]))
    _validate_rows(rows, manifest["device_id"])

    ends = [origin + timedelta(seconds=end) for end in manifest["window_ends_sec"]]
    return TrialData(
        trial_id=trial["trial_id"],
        scenario_id=scenario["scenario_id"],
        title=scenario["title"],
        split=trial["split"],
        seed=trial["seed"],
        truth=scenario["truth"],
        expected=scenario["expected"],
        onset_sec=scenario["onset_sec"],
        anomaly=anomaly,
        notes=scenario["notes"],
        rows=rows,
        window_ends=ends,
        window_ends_sec=list(manifest["window_ends_sec"]),
        decision_end_sec=manifest["decision_window_end_sec"],
    )


def _validate_rows(rows: list[dict], device_id: str) -> None:
    from edge.contracts.models import validate_raw_observation

    for row in rows:
        observation = validate_raw_observation(row)
        if observation.device_id != device_id:
            raise ValueError("generator produced a foreign device")
        if observation.event_time is not None and observation.event_time > observation.received_at:
            raise ValueError("generator produced a future event")


def generate_trials(
    manifest: dict | None = None, *, scenario_ids: list[str] | None = None
) -> list[TrialData]:
    manifest = load_manifest() if manifest is None else manifest
    scenarios = {scenario["scenario_id"]: scenario for scenario in manifest["scenarios"]}
    trials = expand_trials(manifest)
    if scenario_ids is not None:
        unknown = set(scenario_ids) - set(scenarios)
        if unknown:
            raise ValueError(f"unknown scenarios: {sorted(unknown)}")
        trials = [trial for trial in trials if trial["scenario_id"] in set(scenario_ids)]
    return [generate_trial(trial, scenarios[trial["scenario_id"]], manifest) for trial in trials]
