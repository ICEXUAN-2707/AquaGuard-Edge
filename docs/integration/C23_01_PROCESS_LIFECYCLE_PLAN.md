# C23-01: communication process feasibility

Status: design increment; no live cloud, Worker registration or release approval.

## Baseline and boundaries

C22_STAGE_CLOSEOUT records 190 historical local passes. The workspace also contains
uncommitted Scheme A experiments and a feasibility report recording 214 historical
passes. Neither count is a newly executed test. Preserve those artifacts and compare
both routes before a final choice. User reports the cloud device offline; cause is
unknown and this observation is not evidence of an adapter failure.

Parent owns SQLite, leases, immutable payload and final delivery accounting. Child
owns one network attempt and never opens the database. Do not change A/B contracts,
Mock behavior, Worker/CLI, credentials or dependency pins. Integration is separate.

## 01a design contract

Use Windows spawn with a top-level child entry and guarded launcher. Start with one
child per attempt and no descendants. No replacement while previous ownership is
unresolved. Secrets must not appear in command lines, logs or result messages.

States: NEW -> STARTING -> RUNNING -> STOPPING -> REAPED. Any unconfirmed exit or
failed IPC cleanup enters CLEANUP_FAILED, retaining handles and blocking replacement.
Track delivery outcome separately from cleanup outcome; preserve an observed PUBACK
even if subsequent cleanup fails. PUBACK is transport evidence, not business receipt.

One monotonic shutdown deadline covers cooperative stop, terminate, kill if needed,
exit confirmation and IPC cleanup. Repeated close does not renew it. Sending a kill
request is not exit confirmation. Do not claim arbitrary OS calls are cancellable.
Proposed responsive-OS shutdown SLO: 5 seconds total, cooperative phase at most 0.5s,
terminate observation until elapsed 2s, remaining time for kill/join/IPC. All waits
use the original remaining budget. These are prototype targets, not proven bounds.

Result identity includes protocol version, generation, message_id and attempt_token.
Use bounded JSON bytes with explicit schema/type/size checks; no pickle result
deserialization. Parent validates identity and its own receipt deadline before accepting
results. A result received before deadline remains eligible even if cleanup is later.
Unknown outcome permits duplicate delivery on retry; stable message IDs and future
cloud deduplication are required. No exactly-once claim.

## IPC decision gate

Do not put blocking send/recv or multiprocessing Queue feeder threads on the shutdown
coordinator. Connection.poll alone does not guarantee a complete frame is available.
Before 01b implementation choose and prove a Windows-compatible cancellable transport
(bounded nonblocking local stream or overlapped pipe), with partial-frame, full-buffer,
peer-death, authentication and handle-inheritance tests. Separate stop signaling from
payload backpressure. Parent-death containment needs an explicit tested Windows policy;
do not assume child termination follows parent exit.

## Small issues and exit criteria

01a: review lifecycle, IPC choice, parent-death policy and startup cancellation boundary.
Exit only when ownership and timeout behavior are specified for each failure path.
Current unresolved gates: concrete IPC transport, parent-death containment, Process.start
blocking behavior. This document does not close those gates.

01b: isolated supervisor/child experiment, not production adapter. Verify spawn/import
failure, blocked child, abnormal exit, malformed/partial/full IPC, stale generation,
deadline race, repeated close and cleanup failure. No successful close with a live child
or unreleased IPC owner. Retain original outcome on cleanup failure.

01c: real Paho local TLS-stall experiment, normal local session and repeated cycles.
Observe child exit, peer EOF and process/handle drift. TIME_WAIT is not by itself a leak.
Record OS, Python, Paho version, SHA, durations and XML. Compare against existing Scheme A
evidence before deciding the Demo route. No actual IoTDA traffic at this stage.

## Human responsibilities

Developer: implement, automate failure checks, review evidence, repair defects and
provide reproducible commands. User: target-Windows reproduction and later isolated
IoTDA instance/device/CA preparation; keep credentials local. Cloud acceptance requires
matching local message identity, PUBACK, console trace and actual business processing
as separate evidence. No human cloud action is required for 01a/01b.

## 2026-11-10 increment: result framing

Added experiments/process_frames.py and tests/test_process_frames.py. The incremental
decoder caps frames at 4096 bytes, rejects duplicate/unknown fields, wrong identity,
invalid version/status, trailing frames and incomplete EOF. Error text does not echo
wire input. Result channel permits one terminal frame. This decoder does not implement
transport authentication, IO cancellation, parent receipt deadlines or process cleanup;
PUBACK here is a validated status string, not independently proven MQTT evidence.

Executed only the new test file: 14 passed in 0.26s, exit 0. Local XML:
audit/c23-frames-01.xml. No full regression or cloud run; historical counts unchanged.
Actual transport/backpressure, parent-death containment and startup cancellation gates
remain open. No claim that 01a or 01b is complete. No commit/push.

## Isolated worktree and channel increment

All subsequent C23 edits belong to .c23-process on branch
feat/c23-process-isolation-20261110, based on 5100d8248590482c64602efb39b485a7d2005ed7.
Only the three earlier C23 files were copied in. Root C23 originals are preserved;
do not use them as the latest working copy. Root Scheme A experiments are not copied
or modified. Another window owns stage closeout. No checkout/reset/cleanup in its tree.
The existing root virtual environment is reused as an interpreter, without installing
or modifying dependencies. Reports and temporary files belong to this worktree.

Added process_channel.py: nonblocking socket reader/writer with bounded pending bytes,
one IO operation per step and explicit idempotent close. No background helper threads.
Real local socketpair tests cover partial messages with a stalled peer, incomplete EOF,
full send buffer and close, plus roundtrip. These are same-process transport tests;
socket transfer under Windows spawn, endpoint authentication, child ownership and
parent-death containment are not yet proven. No process supervisor is implemented.

Executed frames + channel tests: 18 passed in 0.39s, exit 0. Report:
audit/c23-channel-01.xml in this worktree. Includes the prior 14 frame cases; do not add
14 and 18 as unique cases. Four channel cases are new. No broader regression or cloud
validation. Next issue: spawn socket handoff/ownership and abnormal child exit harness,
then parent-death policy and supervisor. Cloud reconnection is not required yet.
