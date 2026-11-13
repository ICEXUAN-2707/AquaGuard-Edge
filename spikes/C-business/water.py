"""prototype_only: trusted raw water ingress, durable policy state and timers.

No network or user-facing endpoint. DEVICE_SYNCED/EDGE_MAPPED are deliberately
rejected until A supplies a reviewed clock-evidence interface.
"""
import hashlib
import json
from uuid import uuid4

from edge.contracts.models import SafetySignal, validate_raw_observation, _aware
from policy import Policy, evaluate
from store import Store, Conflict, canonical, begin_immediate


class WaterService(Store):
    def __init__(self, path):
        super().__init__(path)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS water_state (
                    device_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS water_inputs (
                    observation_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
                    boot_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
                    UNIQUE(device_id,boot_id,seq));
                CREATE TABLE IF NOT EXISTS water_boots (
                    device_id TEXT NOT NULL, boot_id TEXT NOT NULL,
                    PRIMARY KEY(device_id,boot_id));
            """)

    @staticmethod
    def config(policy, version):
        if not isinstance(policy, Policy) or not isinstance(version,str) or not version.strip():
            raise ValueError("explicit Policy and nonempty version required")
        return canonical(dict(version=version,ttl=policy.ttl_seconds,clear=policy.clear_seconds))

    @staticmethod
    def active(db, device):
        row=db.execute("SELECT body FROM events WHERE device_id=? AND event_type='WATER_CONTACT' AND lifecycle='OPEN'",(device,)).fetchone()
        return None if row is None else json.loads(row[0])

    def ingest(self, payload, *, now, policy, policy_version, trusted_device, trusted_source,
               escalation_level, fault_at=None):
        observation=validate_raw_observation(payload)
        clock=_aware(now)
        config=self.config(policy,policy_version)
        if observation.sensor_type != "water":
            raise ValueError("water ingress requires water observation")
        if observation.device_id != trusted_device or observation.source != trusted_source:
            raise ValueError("trusted device/source mismatch")
        if observation.time_basis != "RECEIVED_FALLBACK":
            raise ValueError("mapped/synced clock evidence interface not implemented")
        if observation.received_at > clock:
            raise ValueError("future receipt")
        if escalation_level not in ("L0","L1","L2","L3"):
            raise ValueError("invalid escalation level")
        # Ignore redelivery receipt time when checking immutable measurement identity.
        content=observation.model_dump(mode="json")
        content.pop("received_at")
        fingerprint=canonical(content)
        with self.connection() as db:
            begin_immediate(db)
            prior=db.execute("SELECT body FROM water_inputs WHERE observation_id=? OR (device_id=? AND boot_id=? AND seq=?)",
                             (observation.observation_id,observation.device_id,observation.boot_id,observation.seq)).fetchall()
            if prior:
                if len(prior)!=1 or prior[0][0]!=fingerprint:
                    raise Conflict("observation identity/content conflict")
                return dict(status="DUPLICATE",event=self.active(db,trusted_device))
            row=db.execute("SELECT body FROM water_state WHERE device_id=?",(trusted_device,)).fetchone()
            state=None if row is None else json.loads(row[0])
            event=self.active(db,trusted_device)
            if event and event["origin"] != trusted_source:
                raise Conflict("origin change requires reviewed merge policy")
            if state:
                if state["source"] != trusted_source:
                    raise Conflict("water state source change requires reviewed policy")
                if clock < _aware(state["evaluated_at"]) or observation.received_at < _aware(state["evaluated_at"]):
                    raise Conflict("out-of-order clock or observation")
                if observation.boot_id == state["boot_id"]:
                    if observation.seq <= state["seq"] or observation.uptime_ms < state["uptime_ms"]:
                        raise Conflict("out-of-order sequence/uptime")
                elif db.execute("SELECT 1 FROM water_boots WHERE device_id=? AND boot_id=?",(trusted_device,observation.boot_id)).fetchone():
                    raise Conflict("retired boot")
            reset=state is None or state["boot_id"]!=observation.boot_id or state["config"]!=config
            dry=None if reset else state["dry_since"]
            previous=None if reset else state["previous_dry_at"]
            wet=observation.value.wet
            signal=SafetySignal.model_validate(dict(
                schema_version="1.1",signal_id=hashlib.sha256(observation.observation_id.encode()).hexdigest(),
                device_id=trusted_device,signal_type="WATER_CONTACT",observed_at=observation.received_at.isoformat(),
                value=wet is True,quality="VALID" if observation.quality=="valid" else observation.quality.upper(),
                observation_refs=[observation.observation_id],origin=trusted_source)).model_dump(mode="json")
            decision=evaluate(signal,event,now=clock,policy=policy,
                              dry_since=None if dry is None else _aware(dry),
                              previous_dry_at=None if previous is None else _aware(previous))
            if event is None and decision.create_event:
                event=dict(schema_version="1.1",event_id=str(uuid4()),device_id=trusted_device,event_type="WATER_CONTACT",
                           lifecycle="OPEN",ack_status="UNACKNOWLEDGED",physical_status="ACTIVE",escalation_level=escalation_level,
                           version=1,created_at=now,origin=trusted_source)
                event=self._write(db,event,kind=decision.reason,now=now,actor="safety",refs=signal["observation_refs"],fault_at=fault_at)["event"]
            elif event and event["physical_status"]!=decision.physical_status:
                event.update(physical_status=decision.physical_status,version=event["version"]+1)
                event=self._write(db,event,kind=decision.reason,now=now,actor="safety",refs=signal["observation_refs"],fault_at=fault_at)["event"]
            state=dict(boot_id=observation.boot_id,seq=observation.seq,uptime_ms=observation.uptime_ms,source=trusted_source,
                       observed_at=observation.received_at.isoformat(),evaluated_at=now,config=config,
                       dry_since=None if decision.dry_since is None else decision.dry_since.isoformat(),
                       previous_dry_at=observation.received_at.isoformat() if decision.dry_since is not None else None,
                       observation_id=observation.observation_id)
            db.execute("INSERT INTO water_inputs VALUES(?,?,?,?,?)",(observation.observation_id,trusted_device,observation.boot_id,observation.seq,fingerprint))
            db.execute("INSERT OR IGNORE INTO water_boots VALUES(?,?)",(trusted_device,observation.boot_id))
            db.execute("INSERT INTO water_state VALUES(?,?) ON CONFLICT(device_id) DO UPDATE SET body=excluded.body",(trusted_device,canonical(state)))
            if fault_at=="state":
                raise RuntimeError("injected water state failure")
            return dict(status="APPLIED",event=event,signal=signal)

    def expire(self, device_id, *, now, policy, policy_version, fault_at=None):
        clock=_aware(now)
        config=self.config(policy,policy_version)
        with self.connection() as db:
            begin_immediate(db)
            row=db.execute("SELECT body FROM water_state WHERE device_id=?",(device_id,)).fetchone()
            if row is None:
                raise ValueError("no water state")
            state=json.loads(row[0])
            if config!=state["config"]:
                raise Conflict("policy change requires a new observation")
            if clock<_aware(state["evaluated_at"]):
                raise Conflict("timer clock moved backwards")
            event=self.active(db,device_id)
            if (clock-_aware(state["observed_at"])).total_seconds()>policy.ttl_seconds:
                state.update(dry_since=None,previous_dry_at=None)
                if event and event["physical_status"]!="UNKNOWN":
                    event.update(physical_status="UNKNOWN",version=event["version"]+1)
                    event=self._write(db,event,kind="WATER_EVIDENCE_EXPIRED",now=now,actor="timer",
                                      refs=[state["observation_id"]],fault_at=fault_at)["event"]
            state["evaluated_at"]=now
            db.execute("UPDATE water_state SET body=? WHERE device_id=?",(canonical(state),device_id))
            if fault_at=="state":
                raise RuntimeError("injected water state failure")
            return event
