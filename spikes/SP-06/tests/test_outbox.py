import json

import pytest

from spike import apply_transition, connect, initialize, process_one


def seed(db_path):
    initialize(db_path)
    return apply_transition(
        db_path,
        event_id="event-1",
        expected_version=0,
        new_state="OPEN",
        idempotency_key="open-1",
        transition_id="transition-1",
        message_id="message-stable-1",
        payload={"action": "open", "source": "simulation"},
    )


def outbox_row(db_path):
    with connect(db_path) as db:
        return db.execute("SELECT * FROM outbox").fetchone()


def test_retry_keeps_message_id_and_separates_receipts(tmp_path):
    db_path = tmp_path / "retry.sqlite"
    seed(db_path)
    outcomes = iter([
        {"status": "RETRY_WAIT", "error": "temporary mock outage"},
        {
            "status": "ACCEPTED",
            "transport_receipt": {"provider": "mock", "receipt_id": "tx-1"},
        },
    ])
    sent_ids = []

    def sender(message):
        sent_ids.append(message["message_id"])
        return next(outcomes)

    assert process_one(db_path, sender) == "RETRY_WAIT"
    first = outbox_row(db_path)
    assert first["status"] == "RETRY_WAIT"
    assert first["attempts"] == 1
    assert first["transport_receipt"] is None

    assert process_one(db_path, sender) == "ACCEPTED"
    second = outbox_row(db_path)
    assert second["status"] == "ACCEPTED"
    assert second["attempts"] == 2
    assert sent_ids == ["message-stable-1", "message-stable-1"]
    assert json.loads(second["transport_receipt"])["receipt_id"] == "tx-1"
    assert second["business_receipt"] is None


def test_business_receipt_is_written_only_when_separately_returned(tmp_path):
    db_path = tmp_path / "business-receipt.sqlite"
    seed(db_path)

    process_one(
        db_path,
        lambda _message: {
            "status": "ACCEPTED",
            "transport_receipt": {"provider": "mock", "receipt_id": "tx-2"},
            "business_receipt": {"provider": "mock-consumer", "receipt_id": "biz-2"},
        },
    )

    row = outbox_row(db_path)
    assert json.loads(row["transport_receipt"])["receipt_id"] == "tx-2"
    assert json.loads(row["business_receipt"])["receipt_id"] == "biz-2"


def test_permanent_mock_failure_is_visible(tmp_path):
    db_path = tmp_path / "failed.sqlite"
    seed(db_path)

    assert process_one(
        db_path,
        lambda _message: {"status": "FAILED", "error": "permanent mock rejection"},
    ) == "FAILED"
    row = outbox_row(db_path)
    assert row["status"] == "FAILED"
    assert row["last_error"] == "permanent mock rejection"


def test_sender_exception_becomes_visible_retryable_error(tmp_path):
    db_path = tmp_path / "sender-error.sqlite"
    seed(db_path)

    assert process_one(db_path, lambda _message: (_ for _ in ()).throw(TimeoutError("mock timeout"))) == "RETRY_WAIT"
    row = outbox_row(db_path)
    assert row["status"] == "RETRY_WAIT"
    assert row["last_error"] == "mock timeout"
    assert row["attempts"] == 1


def test_accepted_result_requires_transport_receipt(tmp_path):
    db_path = tmp_path / "receipt-required.sqlite"
    seed(db_path)

    with pytest.raises(ValueError, match="requires a transport receipt"):
        process_one(db_path, lambda _message: {"status": "ACCEPTED"})

    assert outbox_row(db_path)["status"] == "SENDING"
