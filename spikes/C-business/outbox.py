"""prototype_only: leased Mock-only delivery. No IoTDA SDK or network calls."""
from datetime import timedelta
import json
import math
from uuid import uuid4

from edge.contracts.models import CloudSyncRecord, SafetyEvent, EventTransition, Receipt, _aware
from store import Store, canonical, Conflict


class Worker(Store):
    def __init__(self,path,*,base_delay=1,cap_delay=60,lease_seconds=10,max_attempts=5):
        for value in (base_delay,cap_delay,lease_seconds):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                raise ValueError("finite positive worker durations required")
        if cap_delay<base_delay or isinstance(max_attempts,bool) or not isinstance(max_attempts,int) or not 1<=max_attempts<=100:
            raise ValueError("invalid retry policy")
        self.base,self.cap,self.lease,self.maximum=base_delay,cap_delay,lease_seconds,max_attempts
        super().__init__(path)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS delivery_attempts (
                token TEXT PRIMARY KEY, message_id TEXT NOT NULL, number INTEGER NOT NULL,
                claimed_at TEXT NOT NULL, lease_until TEXT NOT NULL, result TEXT,
                UNIQUE(message_id,number))""")
            db.execute("CREATE TABLE IF NOT EXISTS delivery_policy (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body TEXT NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            config=canonical(dict(version="mock-r05-v1",base=base_delay,cap=cap_delay,lease=lease_seconds,maximum=max_attempts))
            previous=db.execute("SELECT body FROM delivery_policy WHERE singleton=1").fetchone()
            if previous and previous[0]!=config:
                raise ValueError("worker policy changed; reviewed migration required")
            db.execute("INSERT OR IGNORE INTO delivery_policy VALUES(1,?)",(config,))

    def delay(self,attempts):
        return min(self.cap,self.base*2**min(attempts-1,100))

    @staticmethod
    def save(db,record):
        value=CloudSyncRecord.model_validate(record).model_dump(mode="json")
        db.execute("UPDATE outbox SET body=? WHERE transition_id=?",(canonical(value),value["transition_id"]))

    def retry(self,record,now,error):
        record.update(sync_status="FAILED" if record["attempts"]>=self.maximum else "RETRY_WAIT",
                      next_retry_at=None if record["attempts"]>=self.maximum else (now+timedelta(seconds=self.delay(record["attempts"]))).isoformat(),
                      last_error=error)

    def claim(self,*,now):
        clock=_aware(now)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows=db.execute("SELECT body FROM outbox ORDER BY rowid").fetchall()
            candidate=None
            for row in rows:
                record=CloudSyncRecord.model_validate(json.loads(row[0])).model_dump(mode="json")
                if record["sync_status"]=="SENDING":
                    prior=db.execute("SELECT token,claimed_at,lease_until FROM delivery_attempts WHERE message_id=? AND number=?",(record["message_id"],record["attempts"])).fetchone()
                    if prior is None:
                        raise ValueError("SENDING record has no durable attempt")
                    if clock<_aware(prior["claimed_at"]):
                        raise ValueError("worker clock moved backwards")
                    if clock>=_aware(prior["lease_until"]):
                        db.execute("UPDATE delivery_attempts SET result=? WHERE token=?",(canonical(dict(status="LEASE_EXPIRED")),prior["token"]))
                        self.retry(record,clock,"MOCK_LEASE_EXPIRED")
                        self.save(db,record)
                due=record["sync_status"]=="PENDING" or (record["sync_status"]=="RETRY_WAIT" and clock>=_aware(record["next_retry_at"]))
                if due and record["origin"]!="simulation":
                    record.update(sync_status="FAILED",next_retry_at=None,last_error="MOCK_SOURCE_NOT_ALLOWED")
                    self.save(db,record)
                    continue
                if due and record["attempts"]>=self.maximum:
                    record.update(sync_status="FAILED",next_retry_at=None,last_error="MOCK_ATTEMPTS_EXHAUSTED")
                    self.save(db,record)
                    continue
                if candidate is None and due:
                    candidate=record
            if candidate is None:
                return None
            record=candidate
            row=db.execute("SELECT body FROM outbox_payloads WHERE transition_id=?",(record["transition_id"],)).fetchone()
            if row is None:
                raise ValueError("immutable payload missing; legacy database requires reviewed migration")
            payload=json.loads(row[0])
            event=SafetyEvent.model_validate(payload["event"])
            transition=EventTransition.model_validate(payload["transition"])
            if event.created_at>clock or transition.occurred_at>clock:
                raise ValueError("claim precedes event/transition")
            if (payload["message_id"]!=record["message_id"] or transition.transition_id!=record["transition_id"] or
                event.event_id!=transition.event_id or event.version!=transition.event_version or
                event.origin!=transition.origin or event.origin!=record["origin"]):
                raise ValueError("payload lineage mismatch")
            record.update(sync_status="SENDING",attempts=record["attempts"]+1,next_retry_at=None)
            token=str(uuid4())
            db.execute("INSERT INTO delivery_attempts VALUES(?,?,?,?,?,NULL)",(token,record["message_id"],record["attempts"],now,(clock+timedelta(seconds=self.lease)).isoformat()))
            self.save(db,record)
            return dict(token=token,payload=payload,record=record)

    def finish(self,token,result,*,now):
        clock=_aware(now)
        if not isinstance(result,dict) or set(result)-{"status","transport_receipt","business_receipt","error"} or result.get("status") not in ("ACCEPTED","RETRY_WAIT","FAILED"):
            raise ValueError("invalid Mock outcome")
        result=dict(result)
        if result["status"]=="ACCEPTED":
            receipt=Receipt.model_validate(result.get("transport_receipt"))
            if receipt.provider!="mock" or receipt.received_at>clock:
                raise ValueError("only non-future Mock transport receipts accepted")
            result["transport_receipt"]=receipt.model_dump(mode="json")
            if result.get("business_receipt") is not None:
                business=Receipt.model_validate(result["business_receipt"])
                if business.provider!="mock-consumer" or business.received_at>clock:
                    raise ValueError("invalid Mock business receipt")
                result["business_receipt"]=business.model_dump(mode="json")
        elif result.get("transport_receipt") is not None or result.get("business_receipt") is not None:
            raise ValueError("failure must not invent receipts")
        # Persist only controlled diagnostics, never arbitrary adapter exception text.
        result["error"] = None if result["status"]=="ACCEPTED" else "MOCK_TEMPORARY_FAILURE" if result["status"]=="RETRY_WAIT" else "MOCK_PERMANENT_FAILURE"
        fingerprint=canonical(result)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt=db.execute("SELECT * FROM delivery_attempts WHERE token=?",(token,)).fetchone()
            if attempt is None:
                raise ValueError("unknown attempt")
            if clock<_aware(attempt["claimed_at"]):
                raise ValueError("result precedes claim")
            if result["status"]=="ACCEPTED" and _aware(result["transport_receipt"]["received_at"])<_aware(attempt["claimed_at"]):
                raise ValueError("receipt precedes claim")
            if attempt["result"] is not None:
                if json.loads(attempt["result"]).get("status")=="LEASE_EXPIRED":
                    return "STALE"
                if attempt["result"]!=fingerprint:
                    raise Conflict("attempt result changed")
                return "DUPLICATE"
            row=db.execute("SELECT body FROM outbox WHERE message_id=?",(attempt["message_id"],)).fetchone()
            record=json.loads(row[0])
            if record["sync_status"]!="SENDING" or record["attempts"]!=attempt["number"] or clock>=_aware(attempt["lease_until"]):
                return "STALE"  # Only claim() recovery may release an expired lease.
            if record["origin"]!="simulation":
                raise ValueError("Mock worker permits simulation records only")
            if result["status"]=="RETRY_WAIT":
                self.retry(record,clock,result["error"])
            else:
                record.update(sync_status=result["status"],next_retry_at=None,last_error=result["error"],
                    transport_receipt=result.get("transport_receipt"),business_receipt=result.get("business_receipt"))
            self.save(db,record)
            db.execute("UPDATE delivery_attempts SET result=? WHERE token=?",(fingerprint,token))
            return record["sync_status"]

    def step(self,*,now,mode="accept"):
        if mode not in ("accept","temporary","permanent","exception"):
            raise ValueError("unsupported Mock mode")
        claimed=self.claim(now=now)
        if claimed is None:
            return "IDLE"
        if claimed["record"]["origin"]!="simulation":
            raise ValueError("Mock worker permits simulation only")
        try:
            if mode=="exception":
                raise TimeoutError("mock injected transport timeout")
            if mode=="accept":
                result=dict(status="ACCEPTED",transport_receipt=dict(provider="mock",receipt_id=claimed["record"]["message_id"],received_at=now))
            else:
                result=dict(status="FAILED" if mode=="permanent" else "RETRY_WAIT")
        except TimeoutError:
            result=dict(status="RETRY_WAIT")
        return self.finish(claimed["token"],result,now=now)

    def business_receipt(self,message_id,payload,*,now):
        """Independent Mock consumer acknowledgement, never inferred from send."""
        clock=_aware(now)
        receipt=Receipt.model_validate(payload)
        if receipt.provider!="mock-consumer" or receipt.received_at>clock:
            raise ValueError("invalid Mock business receipt")
        value=receipt.model_dump(mode="json")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT body FROM outbox WHERE message_id=?",(message_id,)).fetchone()
            if row is None:
                raise ValueError("unknown message")
            record=CloudSyncRecord.model_validate(json.loads(row[0])).model_dump(mode="json")
            if record["origin"]!="simulation" or record["sync_status"]!="ACCEPTED" or record["transport_receipt"] is None:
                raise ValueError("business receipt requires accepted simulation transport")
            if receipt.received_at<_aware(record["transport_receipt"]["received_at"]):
                raise ValueError("business receipt precedes transport")
            if record["business_receipt"] is not None:
                if record["business_receipt"]!=value:
                    raise Conflict("business receipt changed")
                return "DUPLICATE"
            record["business_receipt"]=value
            self.save(db,record)
            return "BUSINESS"
