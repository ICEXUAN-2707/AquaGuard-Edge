"""prototype_only: single-device-point event transactions; no network IO.

Only trusted, lineage-verified backend signals may call open_water().
TTL/order/boot validation remains the ingestion caller's responsibility.
"""
from contextlib import contextmanager
import json
import math
import sqlite3
from uuid import uuid4

from edge.contracts.models import SafetySignal, SafetyEvent, EventTransition, CloudSyncRecord, _aware
from edge.contracts.api_models import AckRequest, AckResponse, EventDetailResponse


class NotFound(ValueError):
    pass


class Conflict(ValueError):
    pass


class IdempotencyConflict(Conflict):
    pass


class VersionConflict(Conflict):
    def __init__(self, expected, actual):
        self.expected, self.actual = expected, actual
        super().__init__(f"expected {expected}, actual {actual}")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, lifecycle TEXT NOT NULL,
                    body TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS unique_open
                    ON events(device_id,event_type) WHERE lifecycle='OPEN';
                CREATE TABLE IF NOT EXISTS transitions (
                    transition_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    version INTEGER NOT NULL, body TEXT NOT NULL,
                    UNIQUE(event_id,version));
                CREATE TABLE IF NOT EXISTS outbox (
                    transition_id TEXT PRIMARY KEY REFERENCES transitions(transition_id),
                    message_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    key TEXT NOT NULL, request TEXT NOT NULL, response TEXT NOT NULL,
                    PRIMARY KEY(event_id,key));
                CREATE TABLE IF NOT EXISTS outbox_payloads (
                    transition_id TEXT PRIMARY KEY REFERENCES outbox(transition_id),
                    body TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _write(self, db, event, *, kind, now, actor, refs, fault_at=None):
        event = SafetyEvent.model_validate(event).model_dump(mode="json")
        previous=db.execute("SELECT body FROM transitions WHERE event_id=? ORDER BY version DESC LIMIT 1",(event["event_id"],)).fetchone()
        if previous and _aware(now)<_aware(json.loads(previous[0])["occurred_at"]):
            raise ValueError("transition clock moved backwards")
        transition = EventTransition.model_validate(dict(
            schema_version="1.1", transition_id=str(uuid4()), event_id=event["event_id"],
            event_version=event["version"], transition_type=kind, occurred_at=now,
            actor=actor, reason_codes=[kind], evidence_refs=refs, origin=event["origin"],
        )).model_dump(mode="json")
        sync = CloudSyncRecord.model_validate(dict(
            schema_version="1.1", message_id=str(uuid4()), transition_id=transition["transition_id"],
            destination="huawei_iotda", sync_status="PENDING", attempts=0,
            next_retry_at=None, last_error=None, transport_receipt=None,
            business_receipt=None, origin=event["origin"],
        )).model_dump(mode="json")
        db.execute("INSERT INTO events VALUES(?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET lifecycle=excluded.lifecycle,body=excluded.body",
                   (event["event_id"],event["device_id"],event["event_type"],event["lifecycle"],canonical(event)))
        if fault_at == "event":
            raise RuntimeError("injected event failure")
        db.execute("INSERT INTO transitions VALUES(?,?,?,?)", (transition["transition_id"],event["event_id"],event["version"],canonical(transition)))
        if fault_at == "transition":
            raise RuntimeError("injected transition failure")
        db.execute("INSERT INTO outbox VALUES(?,?,?)", (transition["transition_id"],sync["message_id"],canonical(sync)))
        db.execute("INSERT INTO outbox_payloads VALUES(?,?)",(transition["transition_id"],canonical(dict(
            schema_version="1.1",message_id=sync["message_id"],event=event,transition=transition))))
        if fault_at == "outbox":
            raise RuntimeError("injected outbox failure")
        return dict(schema_version="1.1", event=event, transition_id=transition["transition_id"])

    def open_water(self, payload, *, now, escalation_level, ttl_seconds, fault_at=None):
        signal = SafetySignal.model_validate(payload)
        _aware(now)
        if signal.signal_type != "WATER_CONTACT" or signal.quality != "VALID" or signal.value is not True:
            raise ValueError("opening requires a validated active WATER_CONTACT signal")
        if signal.observed_at > _aware(now):
            raise ValueError("future signal")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int,float)) or not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("positive finite TTL required")
        if (_aware(now)-signal.observed_at).total_seconds() > ttl_seconds:
            raise ValueError("stale signal")
        if escalation_level not in ("L0","L1","L2","L3"):
            raise ValueError("invalid escalation level")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM events WHERE device_id=? AND event_type=? AND lifecycle='OPEN'",
                             (signal.device_id,signal.signal_type)).fetchone()
            if row:
                event = json.loads(row["body"])
                if event["origin"] != signal.origin:
                    raise Conflict("origin change requires reviewed merge policy")
                # Return the existing event; repeated paths do not create transitions.
                return event
            event = dict(schema_version="1.1", event_id=str(uuid4()),device_id=signal.device_id,
                         event_type=signal.signal_type,lifecycle="OPEN",ack_status="UNACKNOWLEDGED",
                         physical_status="ACTIVE",escalation_level=escalation_level,version=1,
                         created_at=now,origin=signal.origin)
            return self._write(db,event,kind="WATER_DETECTED",now=now,actor="safety",
                               refs=signal.observation_refs,fault_at=fault_at)["event"]

    def ack(self, event_id, payload, *, now, authorized=False, fault_at=None):
        if authorized is not True:
            raise PermissionError("ACK requires backend authorization")
        request = AckRequest.model_validate(payload).model_dump(mode="json")
        _aware(now)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM events WHERE event_id=?",(event_id,)).fetchone()
            if row is None:
                raise NotFound(event_id)
            prior = db.execute("SELECT request,response FROM operations WHERE event_id=? AND key=?",
                               (event_id,request["idempotency_key"])).fetchone()
            if prior:
                if prior["request"] != canonical(request):
                    raise IdempotencyConflict("idempotency key reused with different request")
                return json.loads(prior["response"])
            event = json.loads(row["body"])
            if event["version"] != request["expected_version"]:
                raise VersionConflict(request["expected_version"],event["version"])
            if event["lifecycle"] != "OPEN":
                raise Conflict("ACK requires OPEN event")
            if _aware(now) < _aware(event["created_at"]):
                raise ValueError("ACK precedes event")
            if event["ack_status"] == "ACKNOWLEDGED":
                tr = db.execute("SELECT transition_id FROM transitions WHERE event_id=? AND version=?",
                                (event_id,event["version"])).fetchone()
                response = dict(schema_version="1.1",event=event,transition_id=tr[0])
            else:
                event.update(ack_status="ACKNOWLEDGED",version=event["version"]+1)
                response = self._write(db,event,kind="ACKNOWLEDGED",now=now,actor="user",refs=[],fault_at=fault_at)
            response = AckResponse.model_validate(response).model_dump(mode="json")
            db.execute("INSERT INTO operations VALUES(?,?,?,?)",(event_id,request["idempotency_key"],canonical(request),canonical(response)))
            if fault_at == "operation":
                raise RuntimeError("injected operation failure")
            return response

    def detail(self, event_id):
        with self.connection() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT body FROM events WHERE event_id=?",(event_id,)).fetchone()
            if row is None:
                raise NotFound(event_id)
            transitions = [json.loads(r[0]) for r in db.execute("SELECT body FROM transitions WHERE event_id=? ORDER BY version",(event_id,))]
            return EventDetailResponse.model_validate(dict(schema_version="1.1",event=json.loads(row[0]),transitions=transitions)).model_dump(mode="json")
