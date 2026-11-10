# MQTT input integration progress — 2026-11-10

Scope: reuse SP-02 ingestion without changing frozen DTOs or granting hardware trust.

## Implemented

SP-02 CLI accepts `--device-id demo01`. Generate, publish and subscribe use the
configured identity and corresponding exact topic. Default prototype01 remains
compatible. Identity hashes are generated for the configured device at creation,
never rewritten after acceptance. Ingress retains commit-before-ACK behavior and
simulation-only source authorization. Topic wildcards, slashes and invalid device
configuration fail before processing/acknowledgement.

Unit verification: 45 passed, 2026-11-10. New tests cover configured identity,
duplicate delivery, topic/device/source spoofing and invalid configuration.
Local report: audit/mqtt-binding-20261110.xml.

Real local Broker reproduction (new output directory each run):

```powershell
..\.venv-app\Scripts\python.exe spikes/SP-02/src/verify_mqtt.py --broker 'C:\Program Files\mosquitto\mosquitto.exe' --directory audit/mqtt-demo01-20261110 --device-id demo01 --port 18885
```

The verifier owns its loopback Broker/client processes and stops them afterwards.
Final run: all five scenarios PASS (duplicate/order, conflict/invalid, client
restart, Broker restart, live subscriber reconnect). Observed resubscription
recovery: 1.0s for this local run only. Evidence: audit/mqtt-demo01-final-20261110.
An initial failed run exposed a callback indentation error introduced in this
increment; it was corrected before the complete rerun. Post-fix unit suite:
45 passed in 0.99s; git diff --check passed.
Payloads remain simulation. Broker persistence is disabled; this is not evidence
of durable Broker recovery or hardware measurement.

## Remaining integration boundary

The public edge runtime still generates its own simulation observations. It does
not yet consume the SP-02 Journal. Existing handoff_b.py is finite, separated by
device/boot, and cannot be treated as a live consumer. b_bridge.py also explicitly
rejects hardware origin. Therefore this change is an input preparation increment,
not MQTT-to-workbench or D1 acceptance.

Next increment: consume durable accepted observations with a persisted cursor,
preserve original received_at and identities, run the fast water path and periodic
checkpoint-backed analysis, and recover idempotently after consumer restart.
Only then review trusted hardware binding and clock/boot evidence. Do not relabel
simulation, replay old data as fresh, or remove source checks to get a demo working.

## Interactive frontend review

Local service is intentionally left running on 127.0.0.1:8020 for user review.
Database: audit/interactive-review-20261110.sqlite. Token is supplied in the task
conversation only; it is a local test credential and is not saved in this document.
The workbench is still a simulation and its Outbox has no real cloud worker.

## D1–D4 status

- D1: simulation MQTT binding prepared; actual rig, calibration and trusted hardware
  input remain unaccepted.
- D2: previous eight browser checks passed; interactive frontend review is ongoing.
- D3: offline C22 groundwork only; real connector, cloud receipts/deployment pending.
- D4: evidence and reproduction notes accumulating; real trials, C0–C3 and final
  report/video/PPT pending. G0 signatures and G1 formal release remain incomplete.
