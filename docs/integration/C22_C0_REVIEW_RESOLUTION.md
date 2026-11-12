# C2.2-C0 review resolution

Baseline: 32dd15d. Review: current task_C2.txt. No Git commit/push or live connection in this task.

## Assessment

The outcome-loss and repeated-close findings are correct and P0 before Paho integration. A cleanup error must be independently observable from delivery facts. Typed client responsibility is also a valid integration gate. The review's remote claims were not reverified here; historical 153-test evidence is local, not GitHub Actions evidence.

## Implemented

Every controlled return from a send attempt now assigns outcome before cleanup. CleanupError.outcome retains accepted, retryable and permanent results, including PUBACK/CONNACK timeout, connect rejection, publish failure and TLS failure. CleanupError is a resource fault, not a business receipt or an instruction to mark a delivery successful.

close permanently stops future sends but retries retained resources even when closed is already true. A failed close retains client ownership and broken status; successful retry clears ownership. Broken transport never resumes sends, including after cleanup eventually succeeds. Repeated close after successful disposal is a no-op. Concurrent close signals stop and wakes waits; serial cleanup remains owned by the send/close sequence.

Added client_protocol.py with typed ClientBinding, MQTTClient and ConnectReason. Binding fixes topic to configured cloud device, QoS1 and retain=false. Future factory binds TLS/auth/client identity, maps VERSION2 codes explicitly and owns disconnect, loop termination and confirmed thread exit. Core accepts normalized transient/protocol/auth connect categories; legacy bool callbacks remain temporarily compatible with Fake clients. The core does not yet enforce a real factory binding because no Paho factory exists.

## Limits and release gates

A stop request cannot interrupt an arbitrary synchronous client method. The blocked-call test proves cancellation is observed after a controlled release, not that an indefinitely blocked DNS/thread can be killed. A real client must demonstrate bounded start/publish/close before release; no daemon timeout workaround.

Typed contract is not proof of IoTDA authentication, Client ID validity, TLS behavior or platform reason-code mappings. Exact Paho/IoTDA mappings remain C1 protocol verification and C2 wrapper work. No Worker integration is included.

Acceptance tests cover success/timeout/rejection/publish/TLS plus cleanup failure; outcome, retained ownership, no reuse and retry disposal; explicit close failure then success; existing concurrent close and blocked-call cancellation; typed transient/protocol connect reasons.

## Next stages

C0: review this contract and cleanup semantics. C1: official MQTT/auth/topic/envelope/limits verification. C2: fixed Paho wrapper with real lifecycle evidence. Then separately integrate Worker policy/provider/fresh finish time. Do not reinterpret later project numbering as completed work: ordering/recovery, cloud consumer idempotency, business receipts and isolated live acceptance all remain separate requirements.

## Validation

Full local C-business suite: 163 passed, 0 failed, 0 skipped in 44.51 seconds. Report: audit/c22-cleanup-20261107.xml (not committed). Diff whitespace checks passed. This is local evidence, not an independent CI run.
