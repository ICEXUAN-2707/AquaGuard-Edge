"""Small, isolated SQLite + Mock Outbox prototype for SP-06.

prototype_only: this is not the production event store or IoTDA adapter.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


class VersionConflict(ValueError):
    """The caller's expected event version is stale."""


class IdempotencyConflict(ValueError):
    """An idempotency key was reused with a different payload."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(db_path: str | Path) -> None:
    """Create the three tables needed by this prototype."""
    db = connect(db_path)
    try:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL CHECK (version >= 1),
                state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transitions (
                transition_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL REFERENCES events(event_id),
                event_version INTEGER NOT NULL CHECK (event_version >= 1),
                idempotency_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                UNIQUE (event_id, event_version),
                UNIQUE (event_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS outbox (
                transition_id TEXT PRIMARY KEY REFERENCES transitions(transition_id),
                message_id TEXT NOT NULL UNIQUE,
                destination TEXT NOT NULL CHECK (destination = 'huawei_iotda'),
                status TEXT NOT NULL CHECK (
                    status IN ('PENDING', 'SENDING', 'RETRY_WAIT', 'ACCEPTED', 'FAILED')
                ),
                attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                payload TEXT NOT NULL,
                last_error TEXT,
                transport_receipt TEXT,
                business_receipt TEXT
            );
            """
        )
        db.commit()
    finally:
        db.close()


def apply_transition(
    db_path: str | Path,
    *,
    event_id: str,
    expected_version: int,
    new_state: str,
    idempotency_key: str,
    transition_id: str,
    message_id: str,
    payload: Mapping[str, Any],
    fault_at: str | None = None,
) -> dict[str, Any]:
    """Atomically update an event and append its Transition and Outbox row.

    For a new event, pass expected_version=0. ``fault_at`` is a test-only
    failure injection point: ``event``, ``transition`` or ``outbox``.
    """
    payload_json = _json(dict(payload))
    request_fingerprint = _json({"new_state": new_state, "payload": dict(payload)})
    db = connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")

        prior = db.execute(
            """SELECT t.transition_id, t.event_version, t.request_fingerprint, o.message_id
               FROM transitions AS t JOIN outbox AS o USING (transition_id)
               WHERE t.event_id = ? AND t.idempotency_key = ?""",
            (event_id, idempotency_key),
        ).fetchone()
        if prior is not None:
            if prior["request_fingerprint"] != request_fingerprint:
                raise IdempotencyConflict("idempotency key reused with different payload")
            db.commit()
            return {
                "event_id": event_id,
                "event_version": prior["event_version"],
                "transition_id": prior["transition_id"],
                "message_id": prior["message_id"],
                "replayed": True,
            }

        current = db.execute(
            "SELECT version FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        actual_version = 0 if current is None else current["version"]
        if actual_version != expected_version:
            raise VersionConflict(
                f"expected event version {expected_version}, found {actual_version}"
            )
        next_version = actual_version + 1

        if current is None:
            db.execute(
                "INSERT INTO events(event_id, version, state) VALUES (?, ?, ?)",
                (event_id, next_version, new_state),
            )
        else:
            db.execute(
                "UPDATE events SET version = ?, state = ? WHERE event_id = ?",
                (next_version, new_state, event_id),
            )
        if fault_at == "event":
            raise RuntimeError("injected failure after event write")

        db.execute(
            """INSERT INTO transitions
               (transition_id, event_id, event_version, idempotency_key, payload,
                request_fingerprint)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                transition_id,
                event_id,
                next_version,
                idempotency_key,
                payload_json,
                request_fingerprint,
            ),
        )
        if fault_at == "transition":
            raise RuntimeError("injected failure after transition write")

        db.execute(
            """INSERT INTO outbox
               (transition_id, message_id, destination, status, payload)
               VALUES (?, ?, 'huawei_iotda', 'PENDING', ?)""",
            (transition_id, message_id, payload_json),
        )
        if fault_at == "outbox":
            raise RuntimeError("injected failure after outbox write")

        db.commit()
        return {
            "event_id": event_id,
            "event_version": next_version,
            "transition_id": transition_id,
            "message_id": message_id,
            "replayed": False,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def claim_one(db_path: str | Path) -> dict[str, Any] | None:
    """Persist a single worker claim before any cloud call is made."""
    db = connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """SELECT transition_id, message_id, destination, payload, attempts
               FROM outbox WHERE status IN ('PENDING', 'RETRY_WAIT')
               ORDER BY rowid LIMIT 1"""
        ).fetchone()
        if row is None:
            db.commit()
            return None
        attempts = row["attempts"] + 1
        db.execute(
            "UPDATE outbox SET status = 'SENDING', attempts = ? WHERE transition_id = ?",
            (attempts, row["transition_id"]),
        )
        db.commit()
        return {
            "transition_id": row["transition_id"],
            "message_id": row["message_id"],
            "destination": row["destination"],
            "payload": json.loads(row["payload"]),
            "attempts": attempts,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def finish_attempt(db_path: str | Path, transition_id: str, result: Mapping[str, Any]) -> str:
    """Persist a Mock Cloud result without changing event facts."""
    status = result.get("status")
    if status not in {"ACCEPTED", "RETRY_WAIT", "FAILED"}:
        raise ValueError("result status must be ACCEPTED, RETRY_WAIT or FAILED")
    transport_receipt = result.get("transport_receipt")
    business_receipt = result.get("business_receipt")
    if status == "ACCEPTED" and transport_receipt is None:
        raise ValueError("ACCEPTED requires a transport receipt")
    db = connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute(
            """UPDATE outbox
               SET status = ?, last_error = ?, transport_receipt = ?, business_receipt = ?
               WHERE transition_id = ? AND status = 'SENDING'""",
            (
                status,
                result.get("error"),
                None if transport_receipt is None else _json(transport_receipt),
                None if business_receipt is None else _json(business_receipt),
                transition_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("transition is not currently SENDING")
        db.commit()
        return str(status)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def recover_sending(db_path: str | Path) -> int:
    """After recreating a single worker, make abandoned claims retryable."""
    db = connect(db_path)
    try:
        cursor = db.execute(
            """UPDATE outbox SET status = 'RETRY_WAIT',
                   last_error = COALESCE(last_error, 'recovered_after_restart')
               WHERE status = 'SENDING'"""
        )
        db.commit()
        return cursor.rowcount
    finally:
        db.close()


def process_one(
    db_path: str | Path,
    sender: Callable[[dict[str, Any]], Mapping[str, Any]],
) -> str | None:
    """Claim and send one message. Sender is a Mock Cloud callable in this Spike."""
    message = claim_one(db_path)
    if message is None:
        return None
    try:
        result = sender(message)
    except Exception as exc:  # A transport error is retryable in this small prototype.
        result = {"status": "RETRY_WAIT", "error": str(exc)}
    return finish_attempt(db_path, message["transition_id"], result)
