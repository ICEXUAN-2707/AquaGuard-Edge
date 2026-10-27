from spike import (
    apply_transition,
    claim_one,
    connect,
    initialize,
    process_one,
    recover_sending,
)


def test_reopen_database_recovers_in_flight_outbox_with_same_id(tmp_path):
    db_path = tmp_path / "restart.sqlite"
    initialize(db_path)
    apply_transition(
        db_path,
        event_id="event-1",
        expected_version=0,
        new_state="OPEN",
        idempotency_key="open-1",
        transition_id="transition-1",
        message_id="message-stable-1",
        payload={"action": "open"},
    )

    claimed_before_restart = claim_one(db_path)
    assert claimed_before_restart["message_id"] == "message-stable-1"
    assert recover_sending(db_path) == 1

    seen = []
    status = process_one(
        db_path,
        lambda message: seen.append(message["message_id"]) or {
            "status": "ACCEPTED",
            "transport_receipt": {"provider": "mock", "receipt_id": "after-reopen"},
        },
    )

    assert status == "ACCEPTED"
    assert seen == ["message-stable-1"]
    with connect(db_path) as db:
        row = db.execute("SELECT status, attempts, message_id FROM outbox").fetchone()
    assert tuple(row) == ("ACCEPTED", 2, "message-stable-1")
