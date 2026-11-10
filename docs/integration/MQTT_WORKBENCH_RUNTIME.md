# Local MQTT → workbench runtime

This increment connects previously separate local processes. No broker is embedded
in the Web application: Mosquitto transports observations, SP-02 commits them to
its Journal before MQTT ACK, and edge consumes that Journal to drive the existing
analysis/events/API/UI. The journal is the durable handoff, not a second simulator.

## Boundaries

- Only demo01, source=simulation, one boot per trial database are allowed.
- The original observation IDs and received_at are preserved. No hardware relabeling.
- Fresh water observations reach the existing fast path; checkpoint-backed windows
  use the same B/C engines as the internal simulation. No cloud worker is enabled.
- Accepted new/out_of_order entries are read in batches of at most 512. Duplicate,
  conflict and invalid journal entries never enter business processing.
- Consumer position and journal path binding survive restart. Bounded input history
  is reloaded; already published context windows are not initialized again.
- Water observations aged 10s or more are not replayed as fresh safety inputs.
  Stale flow endpoints cannot refresh projections. Existing expiry timers continue.
- Within a batch the fast path processes observations in their original receipt
  chronology, then the scheduler evaluates expiry at actual current time. Records
  committed after the sampled tick time are deferred. An observation behind the
  already evaluated water-state watermark fails closed rather than rewinding it;
  delayed/late-water recovery still needs separate acceptance.
- This is one consumer, one local journal and one business DB. Use fresh databases
  per trial; do not replace/truncate a bound journal in place. Boot changes fail
  closed until explicitly reviewed continuous restart/time semantics are implemented.
- Existing 180s in-memory history and demo checkpoint retention limits remain;
  this is not a long-running production service or complete hardware acceptance.

## Start

Use the same Python environment and built web directory as the simulation guide.
Run Mosquitto bound to loopback with an isolated port/config. Initialize an SP-02
Journal using `core.Journal(path).close()` or receive the first valid MQTT message.
Subscribe with the explicit matching device:

```powershell
python spikes/SP-02/src/cli.py subscribe --device-id demo01 --directory audit/my-trial --port 18886 --seconds 600
```

In a separate terminal set the normal token/key and device settings, then:

```powershell
$env:AQUAGUARD_RUNTIME='mqtt'
$env:AQUAGUARD_DEVICE_ID='demo01'
$env:AQUAGUARD_PORT='8021'
$env:AQUAGUARD_DB='audit/my-trial/business.sqlite'
$env:AQUAGUARD_MQTT_JOURNAL='audit/my-trial/journal.sqlite'
python -m edge
```

Set AQUAGUARD_C_TOKEN (at least 24 characters) and AQUAGUARD_C_CURSOR_KEY (at least
32 bytes encoded as hex) explicitly before startup. Open the edge URL and enter
the token. The experiment ID is `mqtt-trial`. MQTT mode generates no observations;
no input means unavailable/expired data rather than invented normal readings.

## Reproducible local integration

```powershell
python spikes/SP-02/src/verify_workbench.py --directory audit/new-mqtt-workbench-run --broker 'C:\Program Files\mosquitto\mosquitto.exe'
```

Use a new directory. The script starts only its own loopback Broker, subscriber,
publisher and public edge service (default ports 18886/8021), sends 45 seconds of
three-source simulation observations, checks live data, WATER_CONTACT, pending
Outbox and a checkpoint-backed mqtt-trial, then stops its owned processes.
It does not modify the separate interactive frontend-review service on port 8020.

## Progress and evidence

Targeted consumer/online tests: 7 passed after fixing restart projection handling.
Full contract/smoke/business regression: 231 passed in 487.86s before the final
batch-boundary increment. Local JUnit: audit/mqtt-runtime-final-20261110.xml.
Real Broker integration PASS: audit/mqtt-workbench-diagnostic-20261110/result.json;
live simulation, WATER_CONTACT, pending Outbox and checkpoint-backed mqtt-trial.
Final boundary tests: 8 passed in 33.81s. Final real Broker repeat: PASS,
audit/mqtt-workbench-release-20261110/result.json. git diff --check passed.
Earlier failed runs are retained. One exposed initialization/path errors in the
verifier; another failed under real scheduling, prompting receipt-batch/deferred
commit handling and additional boundary tests. No new browser acceptance of MQTT mode is implied
by API checks. The previous eight browser checks covered internal simulation.

D1: transport-to-business integration advances, real rig still pending.
D2: same APIs/pages can now be driven by MQTT; interactive 8020 review remains
internal simulation. D3: cloud still offline. D4: local reproducibility artifacts
added; independent real trials and competition materials remain pending.
