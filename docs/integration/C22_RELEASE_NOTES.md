# C2.2 offline configuration, mapping and transport increment

Base: C2.1 d5548b7. This increment is offline groundwork, not completed real IoTDA integration.

## Changes

- cloud_config.py validates test-only device bindings, endpoint, port, CA and timeouts; TLS requires certificate and hostname verification. Secret is excluded from repr; controlled diagnostics avoid supplied values.
- cloud_mapping.py validates immutable snapshot DTOs and lineage, authorizes local devices, preserves stable IDs/version/origin and serializes a deterministic candidate envelope.
- adapters/iotda.py adapts DeliveryRequest to authorization/mapping/transport, rejects request/snapshot ID mismatch and avoids double JSON serialization.
- adapters/iotda_transport.py implements injected-client sequencing, generation/MID matching, callback deadlines, bounded callback storage, controlled errors and cancellation wakeups. CleanupError retains accepted PUBACK evidence; cleanup failure prevents reuse.
- Offline tests cover configuration, mapping, wrapper and transport fault paths. Existing Mock/event/ACK behavior is untouched.

## Limits

No real Paho client factory, authentication, topic/QoS binding, Worker/CLI registration, policy migration, cloud connection or business receipt channel. Injected start/publish/close must obey their nonblocking/bounded contract; cancellation cannot forcibly stop a blocked client call. Fake tests do not prove OS thread cleanup or actual cloud behavior. Error classification and preservation of non-success outcomes on cleanup failure remain follow-up work. The candidate envelope is not yet verified against the official protocol. Existing event-version ordering limitation remains.

## Next milestone

1. Freeze typed Client Protocol: destination identity, topic, QoS1/retain=false, callbacks, error types and shutdown ownership.
2. Refine connection-reason mapping and retain every delivery outcome independently of cleanup failure; deterministic tests for blocked clients/callback races.
3. Verify fixed Paho 2.1.0 and official IoTDA authentication/envelope/limits. Implement a client wrapper only after bounded DNS/TCP/TLS and thread cleanup strategy is established.
4. Separately review persistent channel policy/provider authorization and fresh finish-time integration. Retain legacy Mock databases without silent migration.
5. Run isolated manual device validation only after offline acceptance and explicit operational authorization. Record PUBACK and cloud tracking separately. No production contacts.

## Submission scope

Only C2.2 source, tests and architecture/progress documentation. Exclude user .gitignore edits, task files, Cloud-1 probes, auxiliary scripts, worktrees, test XML/temp DB/cache and credentials. Branch-only push; no main merge.

## Pre-push verification

Full C-business suite: 153 passed, 0 failed, 0 skipped in 45.63 seconds. Local JUnit: audit/c22-push-20261107.xml (excluded from commit). git diff --cached --check passed.
