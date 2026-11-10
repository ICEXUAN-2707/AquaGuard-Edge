# C23-01 local spawn/IPC increment

Date: 2026-11-10. Branch: feat/c23-process-isolation-20261110.
Base: 5100d8248590482c64602efb39b485a7d2005ed7. Uncommitted local increment.
Windows 11 build 26200, Python 3.12.10, Paho 2.1.0.

## Delivered

Bounded JSON result decoder, nonblocking socket channel and Windows spawn lifecycle
probe. Child socket is transferred by spawn; parent closes its duplicate after start.
Each attempt has a fresh generation. No listener, Queue feeder or IO helper thread.
Close joins, terminates, optionally kills and confirms exit before closing process
handle. Repeated close shares its original deadline. Cleanup failure retains ownership
and original outcome. Single-caller experiment only, not a production supervisor.

Synthetic child PUBACK means protocol-test data only. No actual MQTT delivery is
performed. No SQLite, Worker/CLI, A/B contract or cloud modifications. Root stage
closeout and Scheme A files remain unchanged by this increment.

## Verification and cross-check

Initial frames/channel/spawn run: 25 passed in 2.57s. Then added unconfirmed-exit
ownership failure case. Final command:

```
..\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp audit/c23-regression-01 --junitxml audit/c23-regression-01.xml
```

Final: 262 passed, 0 failed, 0 skipped in 70.67s, exit 0. Scope is this isolated
checkout, not the other window's uncommitted work. Counts overlap all preceding runs
and must not be added to historical 190/214 counts. The full scope contains 26 new
C23 cases. Whitespace diff check passed; new untracked files were read/reviewed too.

Cross-check by the same developer, not independent reviewer: partial frame cannot
block coordinator; malformed input fails closed without echo; full socket buffer does
not block writer close; crash/partial EOF does not invent success; result then stalled
child preserves result through termination; unconfirmed exit leaves CLEANUP_FAILED,
retains socket ownership and does not renew deadline. Tests confirm process handle
closed after verified exit. No system-wide handle census or parent-crash test yet.

## Release gates still open

Process.start is synchronous with no demonstrated cancellation bound. No parent-death
containment (e.g. reviewed Windows Job Object policy), concurrent-close support,
cooperative control channel, real Paho TLS-stall child, authenticated task/credential
handoff or system-wide resource drift test. 01a/01b remain PARTIAL; 01c not started.
Next small issue: Windows parent-death containment and startup ownership harness,
then real Paho local-only fault harness. Only then compare final Scheme A/B evidence.

Events/ACK/SQLite Outbox and injected IoTDA transport already exist in the baseline;
their real cloud composition is still gated. End-to-end real sensing -> analysis ->
alarm -> user ACK -> cloud business confirmation is NOT accepted. Device reported
offline by user; no diagnosis inferred. No reconnection required for the next local
issue. Notify user before a separately scoped real IoTDA session.
