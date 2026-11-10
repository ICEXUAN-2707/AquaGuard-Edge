# Frontend workbench — F0/F1/F2

Branch: feat/frontend-workbench-20261110. Base: dd9d3d8.
Worktree: .frontend-workbench. B and C/G1 work continue independently.
No backend, wire contract, database or cloud change is included.

## Delivered

- F0: separate worktree and branch; scope is Web UI, display helpers and frontend
  tests. API changes must be coordinated with C, experiment result contracts with B.
- F1: shared brand/header/navigation, compact credential-loaded/device/source bar,
  collapsible connection settings, desktop/mobile spacing and keyboard focus.
- F2: current situation and independent safety summary, three sensor cards,
  translated reasons with raw codes in expandable details, sync counters and
  event shortcut. No client-invented risk score or decorative data series.
- Unknown uses neutral styling; source and cloud states remain separate. A loaded
  token is described as loaded, not proof of authenticated or online status.
- Pending-event count explicitly refers to the latest 100 returned records.
- Invalid/future browser clock gives unknown age. Original timestamps remain in
  exported backend records; the view uses local Chinese date/time formatting.
- Existing ACK intent, response ordering, polling and backend APIs are reused.

## Validation

- Production build passed; no new frontend dependency.
- State/display tests: 5 passed. ACK uncertain retry and stale response tests remain.
- Chromium browser acceptance: 8 checks passed after layout replacement. 409/503
  are injected frontend scenarios, not real network/server fault acceptance.
- Desktop/mobile screenshots inspected. Final neutral unknown styling and signal
  wording rebuilt; final viewport/error/disconnect capture results are in
  audit/frontend-final-20261110/result.json.
- Evidence stays local under audit/frontend-browser-20261110 and
  audit/frontend-final-20261110. Credentials are not written into these reports.

## Preview

Separate local preview at http://127.0.0.1:8023, internal simulation only.
The earlier 8020 service is not replaced. Token is supplied in the task conversation.
The frontend branch contains the prior backend as its baseline, not later C work.

## Next increments

1. F3: structured event list/detail and Chinese timeline; preserve independent
   lifecycle/physical/ack states, retry intent and conflict review.
2. F4: experiment summary/evidence list now; C0–C3 metrics only after B/C supply
   versioned data. No invented percentages, charts or extra ingestion endpoints.
3. F5: integrate with C's final runtime, MQTT-mode browser acceptance, complete
   responsive/error/keyboard checks, then record a stable delivery version.

## Project status

D1: no hardware progress claimed here. D2: common layout and overview improved;
event/experiment redesign and integration remain. D3: no cloud progress claimed.
D4: frontend screenshots/tests added; experiment report/video/PPT remain outstanding.
G1 remains partial; frontend visual work does not release G2–G4.
