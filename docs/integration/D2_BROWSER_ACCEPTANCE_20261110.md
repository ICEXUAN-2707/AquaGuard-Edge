# D2 browser verification — 2026-11-10

Branch: feat/delivery-closeout-20261109. Baseline b04b648 plus this change.
Real headless Chromium renders built React pages against the public `python -m edge`
simulation service. This is local automated browser verification, not independent
review, real hardware/cloud acceptance or full G1 release.

## Reproduction

1. In web run `npm.cmd ci` and `npm.cmd run build`.
2. Start `python -m edge` using the simulation guide, a fresh database, explicit
   test token/key and a local port. Wait for health; initial analysis takes 32s.
3. Install Playwright in a local tool directory (no production dependency added).
4. Set AQUAGUARD_BROWSER_URL to the localhost service URL, AQUAGUARD_C_TOKEN to
   its test token, AQUAGUARD_PLAYWRIGHT to the absolute Playwright module path,
   AQUAGUARD_CHROMIUM to an installed Chromium executable, and
   AQUAGUARD_BROWSER_EVIDENCE to an evidence output directory.
5. Run `node web/tests/browser-acceptance.cjs` from the repository root.

The script writes result.json and desktop/mobile screenshots without credentials.
Use a fresh database: acknowledgement changes persisted test events. The script
waits for the simulation's water-contact phase rather than creating static events.

## Scope

- Invalid token gives a visible error; valid token connects.
- Overview updates from the continuously running simulation.
- Event details and persisted ACK display separately from physical state.
- Experiment page queries the running demo-trial.
- All three pages have no document horizontal overflow at 390x844.
- Disconnect hides previous experiment data.
- Additional synthetic HTTP 409 and 503 responses exercise conflict and unavailable
  snapshot UI. They are injected by the browser, not evidence of real server faults.

First run: six checks PASS, no browser page errors. Screenshots inspected for
desktop overview and mobile event details; ACKNOWLEDGED coexists with ACTIVE.
Evidence: local audit/browser-20261110 (excluded from Git).
Final expanded run output: audit/browser-final-20261110.
Final result: all eight checks PASS, no browser page errors. 409 and 503 are
synthetic responses; other API requests use the running local backend.

Connection instructions no longer hard-code port 8010; the service URL is authoritative.
Frontend build passed after this text fix.

## Remaining delivery progress

| Deliverable | Verified progress | Still required |
|---|---|---|
| D1 | existing acquisition prototypes; not revalidated here | real three-source wiring, calibration, trial/time evidence and stable physical rig |
| D2 | integrated simulation + real browser three-page checks | trusted hardware integration, real outage/expiry and device-switch scenarios, independent review |
| D3 | C22 offline groundwork integrated; real factory remains gated | lifecycle decision, Worker/CLI integration, IoTDA receipts/recovery, deployed read-only app, CodeArts evidence |
| D4 | closeout baseline and local browser evidence | independent real trials, executable C0–C3 comparison, final report/video/PPT and competition review |

G0 signatures/resources remain pending. G1 is partial with stronger browser evidence.
G2–G4 are not released. Historical backend integration: 227 passed; frontend state:
3 passed. Those suites were not rerun for the connection-instruction-only change.
