"""G1 durable boundary checks; these do not constitute browser/MQTT evidence."""
import pytest

from test_water import WaterService, Policy, Conflict, ingest, observation, time, rows


def test_fast_slow_redelivery_restart_share_one_event(tmp_path):
    service = WaterService(tmp_path / "g1.sqlite")
    first = ingest(service, 0)
    event = first["event"]
    # The second safety path uses the actual lower-level event entry point.
    slow = service.open_water(first["signal"], now=time(0),
                              escalation_level="L2", ttl_seconds=10)
    assert slow == event
    before = rows(service)
    service = WaterService(service.path)
    assert ingest(service, 0, now=1)["status"] == "DUPLICATE"
    assert rows(service) == before
    ack = dict(schema_version="1.1", expected_version=1,
               idempotency_key="g1-ack", ack_type="ACKNOWLEDGE")
    confirmed = service.ack(event["event_id"], ack, now=time(1), authorized=True)
    assert confirmed["event"]["physical_status"] == "ACTIVE"
    assert confirmed["event"]["lifecycle"] == "OPEN"
    ingest(service, 2, False)
    recovered = ingest(service, 4, False)["event"]
    assert recovered["physical_status"] == "CLEARED"
    assert recovered["ack_status"] == "ACKNOWLEDGED"
    assert recovered["lifecycle"] == "OPEN"  # Current policy has no close operation.
    again = ingest(service, 5)["event"]
    assert again["event_id"] == event["event_id"]
    assert again["physical_status"] == "ACTIVE"
    assert again["ack_status"] == "ACKNOWLEDGED"
    detail = service.detail(event["event_id"])
    assert [t["event_version"] for t in detail["transitions"]] == list(range(1, again["version"] + 1))
    assert rows(service)[0] == 1
    assert rows(service)[1] == rows(service)[2]


def test_backlog_does_not_become_fresh_after_restart(tmp_path):
    service = WaterService(tmp_path / "g1.sqlite")
    # Original receipt time is retained across backlog processing.
    delayed = ingest(service, 0, now=11)
    assert delayed["event"] is None
    service = WaterService(service.path)
    assert ingest(service, 0, now=12)["status"] == "DUPLICATE"
    assert rows(service)[0] == 0
    current = ingest(service, 12)["event"]
    assert current["physical_status"] == "ACTIVE"
    service.expire("home01", now=time(23), policy=Policy(10, 2), policy_version="v1")
    before = rows(service)
    with pytest.raises(Conflict, match="out-of-order"):
        ingest(service, 13, now=24)
    assert rows(service) == before
    assert service.detail(current["event_id"])["event"]["physical_status"] == "UNKNOWN"


def test_boot_switch_after_restart_rejects_retired_boot_without_partial_writes(tmp_path):
    service = WaterService(tmp_path / "g1.sqlite")
    event = ingest(service, 0)["event"]
    ingest(service, 1, False)
    service = WaterService(service.path)
    switched = ingest(service, 3, False, boot="b2", seq=0)["event"]
    assert switched["physical_status"] == "UNKNOWN"
    before = rows(service)
    with pytest.raises(Conflict, match="retired boot"):
        ingest(service, 4, boot="b1")
    assert rows(service) == before
    assert ingest(service, 5, False, boot="b2", seq=1)["event"]["physical_status"] == "CLEARED"
    assert rows(service)[0] == 1
