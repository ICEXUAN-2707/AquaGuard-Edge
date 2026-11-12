# D1–D4 delivery closeout

Approved scope: real observations drive one system through sensing, analysis,
alarm, user acknowledgement and cloud synchronization, with reproducible evidence.
Authority: `../AquaGuard_Edition11_Topic1_PlanB_V1.0/00_DELIVERY_BASELINE_V1.0.md`.

## Baseline (2026-11-09)

- Remote main: ad40d93a784576767271cb0701d37382a506f1f0.
- G1 PR #8: open, head 3c5b8c0; integrated here, not merged into main.
- C22: remote/local head 5100d82 before integration; no unpushed commits on that branch.
- Original checkout has modified .gitignore and untracked experiments/evidence.
  They remain untouched; none were imported into this worktree.
- Integration branch: feat/delivery-closeout-20261109, separate .delivery-closeout worktree.
- Historical test counts are reports, not current acceptance. No hardware/cloud,
  browser acceptance, independent sign-off or competition compliance is inferred.

## Work items and gates

IDs below are planning IDs, not GitHub issue numbers. Reuse existing DL issues.

| Item | Deliverable / gate | Owner | Dependency | Exit evidence |
|---|---|---|---|---|
| DL-001 | All / G0 | C coordinates A+B | frozen software contract | actual signatures, reviewer, resource register, hashes |
| DL-002/003/005/006 | D2 / G1 | C integration, B analysis, A input | DL-001 software baseline | continuous runtime, three-page browser and narrow-screen checks, ACK/conflict/expiry logs |
| DL-004 | D1 / G2 | A, B time review | G1, verified hardware | wiring, calibration, raw three-source trials, boot/time mapping |
| DL-007/009 | D3 / G2 | C | bounded connector, test resources | real IoTDA receipts, WAN recovery, accessible cloud Web and running read-only API |
| DL-008 | D3+D4 / G4 | C coordinates team | CodeArts access | real development task, commit and build evidence |
| DL-010 | D4 / G3 | B, A collection | real independent trials | executable C0–C3, trial-separated split, metrics, limitations and model version |
| DL-011 | All / G4 | C coordinates team | previous gate evidence | clean reproduction, complete video, architecture/report/PPT and reviewer decision |

## Immediate integration

Reuse Python, existing M3–M6, SQLite/Outbox, APIs and React prototype.
G1 and C22 are combined without enabling the blocked real Paho factory.
The Web API proxy now defaults to the same port as the public edge entrypoint;
explicit AQUAGUARD_C_PORT still supports the standalone prototype.

Next: finish combined regression; verify three pages in a browser; establish a
single reproducible launcher/evidence run; then integrate trusted hardware input.
Cloud connector selection must resolve resource ownership before enabling real
Worker/CLI delivery. Hardware access, cloud resources and actual human signatures
must be recorded as external dependencies rather than simulated acceptance.

Do not add microservices, Redis, a generic connector framework or new databases.
Do not count mock transport acceptance as cloud business processing.

## Integration verification

2026-11-09, this worktree: contract + smoke + C-business suite passed:
227 passed in 120.86s, no skips. Command: existing `.venv-app` Python with
`-m pytest tests/contracts tests/smoke spikes/C-business/tests -q -p no:cacheprovider`.
Local JUnit: `../audit/delivery-closeout-20261109.xml` (not committed).
Frontend state tests: `node --test web/tests/c-state.test.js`, 3 passed.
`node --check web/vite.config.js` and `git diff --check` passed.
These results do not close browser, hardware, cloud or human acceptance gates.
