from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from spike import (
    IdempotencyConflict,
    VersionConflict,
    apply_transition,
    connect,
    initialize,
)


def submit(db_path, *, expected_version=0, key="k1", payload=None, suffix="1", fault_at=None):
    return apply_transition(
        db_path,
        event_id="event-1",
        expected_version=expected_version,
        new_state="OPEN",
        idempotency_key=key,
        transition_id=f"transition-{suffix}",
        message_id=f"message-{suffix}",
        payload={"action": "open"} if payload is None else payload,
        fault_at=fault_at,
    )


def count_rows(db_path):
    with connect(db_path) as db:
        return tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("events", "transitions", "outbox"))


def test_transition_commits_event_transition_and_outbox_together(tmp_path):
    db_path = tmp_path / "sp06.sqlite"
    initialize(db_path)

    result = submit(db_path)

    assert result["event_version"] == 1
    assert result["replayed"] is False
    assert count_rows(db_path) == (1, 1, 1)


def test_existing_event_can_advance_one_version(tmp_path):
    db_path = tmp_path / "version-two.sqlite"
    initialize(db_path)
    submit(db_path)

    result = submit(
        db_path,
        expected_version=1,
        key="k2",
        payload={"action": "update"},
        suffix="2",
    )

    assert result["event_version"] == 2
    with connect(db_path) as db:
        event = db.execute("SELECT version, state FROM events WHERE event_id='event-1'").fetchone()
        versions = [row[0] for row in db.execute(
            "SELECT event_version FROM transitions ORDER BY event_version"
        )]
    assert tuple(event) == (2, "OPEN")
    assert versions == [1, 2]


@pytest.mark.parametrize("fault_at", ["event", "transition", "outbox"])
def test_failure_at_each_write_rolls_back_all_rows(tmp_path, fault_at):
    db_path = tmp_path / f"{fault_at}.sqlite"
    initialize(db_path)

    with pytest.raises(RuntimeError, match="injected failure"):
        submit(db_path, fault_at=fault_at)

    assert count_rows(db_path) == (0, 0, 0)


def test_failure_while_updating_existing_event_restores_prior_version(tmp_path):
    db_path = tmp_path / "update-rollback.sqlite"
    initialize(db_path)
    submit(db_path)

    with pytest.raises(RuntimeError, match="injected failure"):
        submit(
            db_path,
            expected_version=1,
            key="k2",
            payload={"action": "update"},
            suffix="2",
            fault_at="outbox",
        )

    with connect(db_path) as db:
        event = db.execute("SELECT version, state FROM events WHERE event_id='event-1'").fetchone()
        versions = [row[0] for row in db.execute(
            "SELECT event_version FROM transitions ORDER BY event_version"
        )]
    assert tuple(event) == (1, "OPEN")
    assert versions == [1]
    assert count_rows(db_path) == (1, 1, 1)


def test_same_idempotency_key_replays_result_but_different_payload_conflicts(tmp_path):
    db_path = tmp_path / "idempotency.sqlite"
    initialize(db_path)
    original = submit(db_path)

    replay = submit(db_path, expected_version=0, suffix="new")
    assert replay["replayed"] is True
    assert replay["transition_id"] == original["transition_id"]
    assert replay["message_id"] == original["message_id"]
    assert count_rows(db_path) == (1, 1, 1)

    with pytest.raises(IdempotencyConflict):
        submit(db_path, payload={"action": "close"}, suffix="conflict")
    with pytest.raises(IdempotencyConflict):
        apply_transition(
            db_path,
            event_id="event-1",
            expected_version=0,
            new_state="CLOSED",
            idempotency_key="k1",
            transition_id="transition-state-conflict",
            message_id="message-state-conflict",
            payload={"action": "open"},
        )
    with pytest.raises(VersionConflict):
        submit(db_path, key="k2", expected_version=0, suffix="stale")


def test_two_sqlite_connections_cannot_both_advance_same_version(tmp_path):
    db_path = tmp_path / "concurrent.sqlite"
    initialize(db_path)
    barrier = Barrier(2)

    def worker(index):
        barrier.wait()
        try:
            return submit(db_path, key=f"k{index}", suffix=str(index))["event_version"]
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (1, 2)))

    assert sorted(map(str, results)) == ["1", "conflict"]
    assert count_rows(db_path) == (1, 1, 1)
