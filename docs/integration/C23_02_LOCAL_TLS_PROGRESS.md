# C23-02 local Paho TLS fault verification

Date: 2026-11-10. All artifacts belong to `.c23-process`.

Verified the existing uncommitted `tls_stall` child path against a loopback TCP
listener using real Paho. The listener receives TLS ClientHello without completing
the handshake. The result deadline expires without inventing PUBACK; closing the
probe confirms child exit and the peer observes EOF or reset. No IoTDA traffic,
credentials, dependency changes, Worker registration or A/B contract changes.

Targeted command (run from this checkout):

```powershell
..\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests/test_process_paho_local.py -q -p no:cacheprovider --junitxml audit/c23-paho-local-01.xml
```

Result: 1 passed in 1.89s, exit 0. XML: `audit/c23-paho-local-01.xml`.
This is one local fault case, not a normal MQTT delivery or cloud receipt test.

Full regression command:

```powershell
..\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp audit/c23-regression-02 --junitxml audit/c23-regression-02.xml
```

Result: 263 passed in 94.10s, exit 0. Includes the targeted case and previous
262-case scope; counts must not be added. Evidence: `audit/c23-regression-02.xml`.

Remaining gates: parent-death containment and startup ownership harness; normal
local MQTT session; repeated-cycle process/handle drift evidence; authenticated
task handoff; cooperative stop and concurrent-close policy. Synchronous
`Process.start()` still has no demonstrated cancellation bound. C23-01a/01b remain
partial and 01c has only the TLS-stall case verified. No production release or
Scheme A/B selection is implied. No independent reviewer participated.
