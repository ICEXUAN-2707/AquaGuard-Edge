"""prototype_only: trusted backend query projections; never changes events."""
import json
import math
from contextlib import nullcontext
from pydantic import ValidationError

from edge.contracts.api_models import LiveSnapshot, AssessmentResponse, ExperimentResult, SyncStatus
from edge.contracts.models import CloudSyncRecord, _aware
from store import Store, NotFound, canonical


class Unavailable(ValueError):
    pass


class Projections(Store):
    def __init__(self,path):
        super().__init__(path)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS query_projections (
                kind TEXT NOT NULL, identity TEXT NOT NULL, captured_at TEXT NOT NULL,
                ttl REAL, body TEXT NOT NULL, PRIMARY KEY(kind,identity))""")

    def publish(self,kind,payload,*,captured_at,ttl_seconds=None,_connection=None):
        """Internal backend only. No HTTP ingestion or client-origin authorization."""
        captured=_aware(captured_at)
        models={"live":LiveSnapshot,"assessment":AssessmentResponse,"experiment":ExperimentResult}
        if kind not in models:
            raise ValueError("unsupported projection kind")
        value=models[kind].model_validate(payload).model_dump(mode="json")
        if kind=="experiment":
            identity=value["trial_id"]
        else:
            if isinstance(ttl_seconds,bool) or not isinstance(ttl_seconds,(int,float)) or not math.isfinite(ttl_seconds) or ttl_seconds<=0:
                raise ValueError("explicit positive finite projection TTL required")
            if kind=="live":
                identity=value["device_id"]
                if _aware(value["captured_at"])!=captured:
                    raise ValueError("live timestamp mismatch")
            else:
                assessment=value["assessment"]
                identity=assessment["device_id"]
                for signal in value["safety_signals"]:
                    if signal["device_id"]!=identity or signal["origin"]!=assessment["origin"] or _aware(signal["observed_at"])>captured:
                        raise ValueError("assessment signal identity/origin/time mismatch")
        with (self.connection() if _connection is None else nullcontext(_connection)) as db:
            if _connection is None:
                db.execute("BEGIN IMMEDIATE")
            prior=db.execute("SELECT captured_at,ttl,body FROM query_projections WHERE kind=? AND identity=?",(kind,identity)).fetchone()
            if prior:
                if _aware(prior[0])>captured:
                    raise ValueError("projection timestamp moved backwards")
                if _aware(prior[0])==captured and (prior[2]!=canonical(value) or prior[1]!=ttl_seconds):
                    raise ValueError("conflicting projection at same timestamp")
            db.execute("INSERT INTO query_projections VALUES(?,?,?,?,?) ON CONFLICT(kind,identity) DO UPDATE SET captured_at=excluded.captured_at,ttl=excluded.ttl,body=excluded.body",
                       (kind,identity,captured_at,ttl_seconds,canonical(value)))

    def read(self,kind,identity,*,now):
        clock=_aware(now)
        with self.connection() as db:
            row=db.execute("SELECT captured_at,ttl,body FROM query_projections WHERE kind=? AND identity=?",(kind,identity)).fetchone()
        if row is None:
            raise NotFound(identity)
        age=(clock-_aware(row[0])).total_seconds()
        if age<0 or (row[1] is not None and age>row[1]):
            raise Unavailable("projection outside validity interval")
        return json.loads(row[2])

    def sync(self,device_id=None):
        with self.connection() as db:
            rows=db.execute("SELECT o.body FROM outbox o JOIN transitions t USING(transition_id) JOIN events e ON e.event_id=t.event_id WHERE (? IS NULL OR e.device_id=?)",(device_id,device_id)).fetchall()
        try:
            records=[CloudSyncRecord.model_validate(json.loads(r[0])) for r in rows]
        except (ValidationError, ValueError, TypeError):
            raise Unavailable("invalid persisted sync record") from None
        receipts=[(r.business_receipt or r.transport_receipt, "BUSINESS" if r.business_receipt else "TRANSPORT")
                  for r in records if r.sync_status=="ACCEPTED" and r.transport_receipt is not None]
        latest=max(receipts,key=lambda item:item[0].received_at) if receipts else None
        return SyncStatus.model_validate(dict(schema_version="1.1",device_id=device_id,
            pending_count=sum(r.sync_status in ("PENDING","SENDING","RETRY_WAIT") for r in records),
            failed_count=sum(r.sync_status=="FAILED" for r in records),
            last_ack_level="NONE" if latest is None else latest[1],
            last_accepted_at=None if latest is None else latest[0].received_at.isoformat())).model_dump(mode="json")
