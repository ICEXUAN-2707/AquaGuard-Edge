# Edge code skeleton

This package is the local service baseline for AquaGuard Edge. It currently
contains startup configuration, a health endpoint, and candidate DTO/API models.
The business routes and persistence adapters are intentionally not implemented
until the contract review passes the C0–C2 gates in
[`docs/contracts/CONTRACT_ACCEPTANCE.md`](../docs/contracts/CONTRACT_ACCEPTANCE.md).

## Current layout

```text
edge/
  __main__.py       Environment validation and local Uvicorn startup
  config.py         Strict local-development settings
  app.py            FastAPI factory and /health endpoint
  contracts/
    models.py       Candidate schema_version 1.1 DTOs and semantic checks
    api_models.py   Candidate request/response DTOs for the planned routes
```

The React/Vite connection page is under `web/`. Python startup and contract
checks are under `tests/`.

## Extension order after contract sign-off

Implement vertical slices in this order: simulated input and normalization,
window alignment, feature extraction, rules-based assessment, event lifecycle
and SQLite transaction boundary, then cloud outbox/sync. Keep hardware and cloud
adapters behind small interfaces so local simulation remains usable without
physical sensors or cloud credentials. Add each slice only after its related
contract gate has an owner decision and acceptance evidence.

## Local baseline

See the root README for environment setup. Set `AQUAGUARD_DEVICE_ID`, then run
`python -m edge`; `/health` reports local service availability and device ID.
This endpoint does not indicate that sensing, alerting, or cloud sync works.
