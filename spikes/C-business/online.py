"""Simulation-only continuous vertical slice using existing B/C engines."""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import hashlib

from b_bridge import publish_window
from alignment import align
from checkpoint import save
from policy import Policy
from projections import Projections
from water import WaterService
from context_events import ContextEvents
from edge.contracts.models import _aware


class Simulation:
    """One scheduler owns this object; injected clocks make trials repeatable.

    No cloud/network calls. Restart begins a new explicit simulation boot.
    History is bounded to 180 seconds; checkpoint retention remains a demo limit.
    """

    def __init__(self, path, checkpoints, start):
        self.water = WaterService(path)
        self.queries = Projections(path)
        self.context = ContextEvents(path)
        self.checkpoints = Path(checkpoints)
        self.start = self.last = start
        self.boot = str(uuid4())
        self.rows = []
        self.sequence = 0
        self.next_end = start + timedelta(seconds=30)
        self.trial='demo-trial'
        self.queries.publish('experiment',dict(schema_version='1.1',trial_id=self.trial,
            source='simulation',status='RUNNING',started_at=start.isoformat(),ended_at=None,
            asset_refs=[]),captured_at=start.isoformat())

    def step(self, now):
        if now.tzinfo is None or now < self.last:
            raise ValueError("aware monotonic clock required")
        if self.sequence and (now-self.last).total_seconds() < 1:
            return None
        elapsed = (now-self.start).total_seconds()
        # Explicit 120-second demo: attended, absent, wet, then dry.
        phase = elapsed % 120
        values = dict(flow=dict(pulse_count=8, interval_ms=1000,
                                estimated_lpm=1.0, calibration_id="simulation-only"),
                      presence=dict(present=phase < 40, moving=phase < 40, still=False),
                      water=dict(wet=70 <= phase < 100))
        for sensor, value in values.items():
            row = dict(schema_version="1.1", observation_id=f"{self.boot}:{sensor}:{self.sequence}",
                       device_id="demo01", sensor_type=sensor, boot_id=self.boot,
                       seq=self.sequence, uptime_ms=int(elapsed*1000), event_time=None,
                       received_at=now.isoformat(), time_basis="RECEIVED_FALLBACK",
                       value=value, quality="valid", source="simulation")
            self.rows.append(row)
            if sensor == "water":
                self.water.ingest(row, now=now.isoformat(), policy=Policy(10, 2),
                    policy_version="g1-simulation-v1", trusted_device="demo01",
                    trusted_source="simulation", escalation_level="L2")
        self.sequence += 1
        self.last = now
        cutoff = (now-timedelta(seconds=180)).isoformat()
        self.rows = [r for r in self.rows if r["received_at"] >= cutoff]
        if now < self.next_end + timedelta(seconds=2):
            return None
        # Publish one current window, never fabricate historical samples on catch-up.
        # Real scheduler ticks are not exact integer seconds. End on an actual
        # flow interval endpoint so the frozen flow terminal-state rule applies.
        cutoff_end=now-timedelta(seconds=2)
        endpoints=[_aware(r['received_at']) for r in self.rows
                   if r['sensor_type']=='flow' and _aware(r['received_at'])<=cutoff_end]
        if not endpoints:
            return None
        end=max(endpoints)
        config = dict(width=30, lateness=2, ttl=10, flow_threshold=0.1)
        window = align(self.rows, [end], **config)["windows"][0]
        fw = save(self.checkpoints, window, self.rows, alignment_config=config)
        self.queries.publish('experiment',dict(schema_version='1.1',trial_id=self.trial,
            source='simulation',status='RUNNING',started_at=self.start.isoformat(),ended_at=None,
            asset_refs=[fw['state_checkpoint_ref']]),captured_at=now.isoformat())
        self.context.ingest(fw,now=now.isoformat(),checkpoint_root=self.checkpoints)
        water_rows=[r for r in self.rows if r['sensor_type']=='water'
                    and r['observation_id'] in window['source_observation_ids']
                    and 0<=(_aware(window['window_end'])-_aware(r['received_at'])).total_seconds()<8]
        signals=[]
        if water_rows:
            water=water_rows[-1]
            signals=[dict(schema_version='1.1',signal_id=hashlib.sha256(water['observation_id'].encode()).hexdigest(),
                device_id='demo01',signal_type='WATER_CONTACT',observed_at=water['received_at'],
                value=water['value']['wet'],quality='VALID',observation_refs=[water['observation_id']],origin='simulation')]
            if signals[0]['value']:
                # The same evidence can reach both paths, sharing Store's unique OPEN key.
                # Never use historical dry to override the raw fast-path state.
                self.water.open_water(signals[0],now=now.isoformat(),escalation_level='L2',ttl_seconds=10)
        assessment = publish_window(self.queries, fw, now=now.isoformat(),
                                    checkpoint_root=self.checkpoints,safety_signals=signals)
        self.next_end = end+timedelta(seconds=5)
        return assessment
