# SP-06 SQLite + Mock Outbox Spike

Status: **IN_PROGRESS** · Owner: **C** · Scope: **`prototype_only`**

This is an isolated technical prototype for SQLite transaction and Outbox
behavior. It does not implement production endpoints or connect to IoTDA.

## Run

From the repository root:

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/SP-06/tests -q -p no:cacheprovider
```

The prototype uses only Python's standard-library `sqlite3` module and the
repository's existing pytest environment. Tests use temporary databases.

## Boundary

- One local SQLite database, one process, one Outbox worker, one destination.
- Mock Cloud only; never place real credentials here.
- Delivery is treated as at least once. Stable `message_id` supports receiver
  deduplication; this prototype does not claim exactly-once delivery.
- No HTTP API, full event lifecycle, hardware adapter, real IoTDA adapter,
  migrations framework, ORM, scheduler, or production retry timing.

See [`REPORT.md`](REPORT.md) for progress and evidence.
For a step-by-step human walkthrough and deterministic JSON cases, see
[`MANUAL_TEST_GUIDE.md`](MANUAL_TEST_GUIDE.md) and [`data/manual_cases.json`](../../../SP-06/data/manual_cases.json).
