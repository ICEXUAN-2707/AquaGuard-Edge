# Next stage: C2.2-C1 protocol verification and C2 implementation preparation

Prerequisite: C0 cleanup fixes and typed client contract. This plan does not authorize live cloud execution or claim Paho is implemented.

## C1 - protocol evidence

Collect official Huawei IoTDA sources for MQTT device authentication, Client ID construction, custom-message topic and envelope, supported QoS, payload size/rate limits, TLS/CA and disconnect policy. Record exact URLs, retrieval date, applicability to instance/region, and candidate vs verified fields. Cross-check mapping without credentials; correct only proven mismatches with regression tests. Never infer business receipt from PUBACK.

Read fixed installed Paho 2.1.0 source and official documentation for VERSION2 CONNACK/PUBACK callbacks, rc and reason mapping, reconnect ownership, connect_async, socket creation and loop shutdown. Produce an explicit code-to-ConnectReason/error table. MQTT 3.1.1 acknowledgement semantics must not be confused with MQTT5 negative PUBACK codes.

Deliver docs/integration/C22_PROTOCOL_EVIDENCE.md and a reviewed client lifecycle proposal. Gate: authentication/topic/envelope/limits each have direct authoritative evidence or are explicitly unresolved. No dependency changes or actual credentials.

## C2 - client wrapper, incremental implementation

1. Add adapters/paho_client.py around the typed client contract, factory injection and explicit ClientBinding enforcement. Bind cloud identity/topic/QoS1/retain=false before any connection. No Worker or CLI registration.
2. Add deterministic VERSION2 reason-code translation and authentication test vectors with dummy credentials. Test mapping output is published unchanged.
3. Prove bounded startup and cleanup. Account separately for DNS, TCP, TLS, CONNACK and publish wait; a timed Event does not cancel blocking calls. If an in-process solution cannot demonstrate resource exit, stop release and review a managed-process boundary; no daemon workaround.
4. Add local-only fault harness for socket/TLS failures and thread lifecycle. Fake tests remain necessary but do not prove real thread termination. Every resource is owned until confirmed disposed; cleanup faults preserve the original delivery result.

Acceptance: original 163 regressions plus new cases pass without skips; no secret in logs/exceptions; correct reason mapping; confirmed resource exit/retry disposal; no cloud requirement for automated suite. Real network evidence is a separate controlled harness, not unannounced IoTDA access.

## Later integration

Separate change for persistent channel policy/provider authorization and fresh finish-time semantics, including old Mock database copies. Keep Store atomicity and immutable payloads. Review event-version ordering, retry exhaustion and outage recovery independently. Only after offline acceptance schedule explicit isolated-device validation; collect PUBACK, cloud tracking and business processing as distinct evidence.

## Commit boundaries

C0: cleanup/outcome/protocol contract plus regressions.
C1: protocol evidence and any separately justified mapping correction.
C2: Paho wrapper and lifecycle tests.
Integration: Worker/CLI/policy compatibility.
No main merge, production contacts, silent database conversion or new infrastructure.
