# C2.2-L1 Paho bounded-exit audit

Date: 2026-11-07. Baseline: a6c51afaeb2b9a81a7457381742ef649e0ab0707.
Disposition: NOT RELEASEABLE for guaranteed bounded resource reclamation.
This audit changes documentation only. No cloud connection, business-code modification, dependency install, subprocess implementation, branch push or merge.

## 1. Opinion assessment and evidence vocabulary

The task is reasonable and appropriately makes lifecycle analysis a P0 gate. Existing 187 passing tests do not establish bounded shutdown. A timed wait/join limits how long that caller waits; it does not terminate the underlying operation or reclaim its resources. Distinguish bounded detection, bounded API return and bounded reclamation.

[S] actual source inspection in this audit; [D] existing deterministic offline tests; [N] existing local network test; [U] unproven. Existing test evidence is audit/c22-lifecycle-verified-20261107.xml, 187 tests, zero errors/failures/skips. It was verified before the baseline commit, not rerun for this documentation-only audit. No GitHub Actions claim.

Paths below are relative to the repository unless marked Python installation. Paho references use the ACTUAL installed .venv-app/Lib/site-packages/paho/mqtt/client.py, version 2.1.0. Python socket references use C:/Program Files/Python312/Lib/socket.py, Python 3.12.10. These are environment source locations, not vendored project code.

## 2. Architecture and ownership

Caller thread: IoTDATransport.send holds serial for the entire attempt, constructs PahoClient, starts it, waits on Events, invokes publish and finally close. Transport.close requests stop/wakes an Event, then waits on serial. See adapters/iotda_transport.py:52,95,167.

Owned network thread: PahoClient.start creates a non-daemon Thread; its run calls synchronous connect(endpoint, port, 60), then client.loop(timeout=.1). VERSION2 callbacks run here normally, but Paho may call packet write/callbacks inline from publish/disconnect too. Do not assume all callbacks run on one thread. See adapters/paho_client.py:39-72; installed Paho _packet_queue:3758, _packet_write:3160.

No Paho loop_start is used. Paho internal _thread therefore remains None; its unbounded loop_stop join is not this wrapper's direct shutdown mechanism, but publish/disconnect can take the inline loop_write path because _thread is None. Installed Paho:2332,2351,3788.

Resource ownership: wrapper owns client and network Thread. Paho owns connection socket and lazily created socketpair. During _create_socket/TLS wrapping, socket may be local to the connect stack: reconnect assigns self._sock only after _create_socket returns (1598). The wrapper currently has no cancellation handle for that in-progress socket or DNS call. GC/client destruction is not a bounded release guarantee.

Transport retains PahoClient after failed cleanup; CleanupError.outcome preserves controlled delivery fact. PahoClient retains Thread after join timeout; repeat close may retry. No future sends are allowed after failure. Retained ownership is correct bookkeeping, not successful cleanup.

## 3. Sequence

```mermaid
sequenceDiagram
    participant C as Caller / Transport
    participant W as PahoClient wrapper
    participant T as Owned non-daemon thread
    participant P as Paho / OS
    C->>W: start(callbacks)
    W->>T: start
    T->>P: getaddrinfo -> per-address TCP connect
    T->>P: TLS handshake (timeout = keepalive)
    T->>P: queue/send MQTT CONNECT
    T->>P: loop(.1), process CONNACK
    P-->>C: callback signals Event
    C->>W: publish(payload)
    W->>P: queue / possibly inline loop_write
    T->>P: loop, process PUBACK
    P-->>C: callback timestamp and Event
    C->>W: close
    W->>W: stop flag; join(close_timeout)
    alt thread still blocked
        W-->>C: cleanup failure; retain ownership
    else thread joined
        W->>P: disconnect (return code ignored)
        W-->>C: disposed=True (socket release not established)
    end
```

## 4. Phase timeout/cancellation matrix

| Phase | Exact blocking path / executing thread | Existing mechanism | Cancellation and bounded reclamation |
| --- | --- | --- | --- |
| DNS | socket.create_connection -> getaddrinfo, socket.py:841,961,978; owned network thread | No application DNS deadline; socket timeout is assigned AFTER resolution at 847 | [S] stop Event cannot cancel getaddrinfo; [U] OS resolver return bound. No guaranteed thread reclamation |
| TCP | Paho _create_socket_connection:4632-4640 -> socket.py:850 sock.connect; network thread | connect_timeout per socket/address; loop across all resolved addresses | [S] per-address wait constrained by socket timeout, not one overall DNS+TCP deadline. No wrapper cancellation handle. Refusal expected promptly but [U] local real refusal test not run |
| TLS | Paho _ssl_wrap_socket:4642; settimeout(_keepalive):4670; do_handshake:4671; network thread | Hardcoded connect(...,60) makes handshake socket timeout nominally 60s | [S,N] .15s connect_timeout does not bound handshake. stop/join cannot interrupt it. Nominal socket timeout is not the configured overall deadline or hard real-time guarantee |
| CONNECT/CONNACK | reconnect:1598-1604 -> _send_connect:3469 -> packet queue/write; then loop:1606/select:1637/_handle_connack:3844 | Transport connect_deadline and Event wait; Paho loop select .1s | [S] protocol wait can time out without cancelling connect; [U] real no-CONNACK cleanup/socket closure. Keepalive is not an independent CONNACK deadline |
| Publish/PUBACK | wrapper publish:74-79; Paho publish:1709, out-message mutex near 1787, _send_publish:3367, _packet_queue:3758; caller plus network callbacks | Transport publish deadline starts before call and checks callback timestamp | [S,D] deadline rejects late callback, but cannot bound synchronous publish/lock/inline writes. PUBACK timeout is unknown delivery outcome |
| Disconnect | wrapper _close_owned:100; Paho disconnect:1873-1896 -> _send_disconnect:3574 -> queue/write | No dedicated disconnect deadline; only called AFTER join | [S] no cancellation or result-code verification; queued/partial disconnect may need further loop writes after wrapper already stopped pump. No proof socket closed |
| Network-loop shutdown | wrapper run:49-52; Paho loop:1606/_loop:1637 | stop checked BETWEEN loop calls, .1s select timeout | [S] timeout bounds select wait only, not callbacks, locks, packet processing or stalled connect. Paho loop_stop:2351-2364 has unbounded join but is not invoked here |
| Thread termination | wrapper _close_owned:86-102 thread.join(close_timeout) | Timed join and is_alive check | [S,D,N] bounds join wait, not lock acquisition, disconnect or thread lifetime. On timeout raises and retains reference. Non-daemon thread may prevent process exit |

Keepalive 60s is MQTT liveness configuration. Paho also reuses it for TLS handshake in this version; that implementation coupling is NOT a sound project handshake deadline. DNS deadline, TCP deadline, TLS deadline, CONNACK deadline, PUBACK deadline and close budget must be explicit and independently justified.

## 5. Cleanup responsibility and defects

P0-1 [S,N]: in-progress DNS/TLS cannot be cancelled by wrapper; join failure leaves a non-daemon thread. Current implementation cannot promise bounded exit.

P0-2 [S]: close_timeout excludes cleanup_lock, wrapper lock and Transport.serial acquisition. publish holds wrapper lock across backend publish. Blocked publish can prevent close even reaching its timed join. Transport.close also waits on send's serial lock. A timed join does not bound the public close API.

P0-3 [S]: join BEFORE disconnect; stopped network pump cannot necessarily flush pending DISCONNECT. Paho._packet_queue calls loop_write inline only in certain conditions. Partial writes may return without fully closing socket. wrapper ignores rc and sets disposed=True. No assertion on socket/socketpair ownership or closure. A dead Thread is not a closed connection. Installed Paho _packet_write:3160-3250 closes socket only when DISCONNECT packet fully sent; _sock_close:1123 and _reset_sockets:1139 own different resources.

P0-4 [S]: no client teardown contract exposing/cancelling an in-flight DNS/TCP/TLS operation. self._sock assignment happens after handshake. Calling disconnect from another thread alone would not fix this. Do not patch private fields without separate ownership design/version review.

P1-1 [S]: post-CONNACK run exceptions are reported through on_connect(failure), but Transport only accepts its first connect result while in connect phase; after READY failure reduces to disconnected and specific cause is lost. Callback errors become PROTOCOL_REJECTED even if they are application defects.

P1-2 [S]: on_disconnect may run via Paho callback and again in wrapper finally. Failure handling should be explicitly idempotent and distinguish expected shutdown from transport loss.

P1-3 [S,D]: concurrent close serializes cleanup, but waiting callers have no shared overall deadline. Retry ownership and successful disposal bookkeeping improved; they are not proof of socket release. close invoked from network callback detects self-join only after acquiring locks; a competing closer waiting in join may create bounded join failure followed by lock delay.

P1-4 [S]: constructor CA/client initialization and callbacks have no lifecycle budget. A supplied backend/callback can violate prompt-return assumptions. Document trust boundary and prevent resource allocations from becoming unowned on constructor failure.

## 6. Failure scenario assessment

| Scenario | Current outcome / resource status | Evidence |
| --- | --- | --- |
| DNS hangs | Transport may report timeout then CleanupError; network thread still in resolver | S; real DNS hang U |
| TCP refused | background NETWORK_FAILURE, then disconnect; eventual join expected | D simulated classification; real refusal U |
| TCP never completes | per-address connect_timeout; DNS and address iteration outside total budget; join may fail | S; real blackhole U |
| TCP accepted, TLS never responds | close join times out and retains live thread; releasing server lets thread finish | N existing loopback test |
| Invalid CA file | config construction refuses before network | D; does not prove bad peer certificate behavior |
| Untrusted peer certificate / hostname mismatch | expected SSLError -> TLS_FAILURE with failed-connect thread exit | S inference; real TLS fixture U |
| Broker rejects auth | VERSION2 reason -> AUTH_REJECTED, Transport permanent failure; cleanup still separate | D pure normalized mapping; real broker U |
| CONNACK absent | Event timeout; thread may be pumping; join/close must be evaluated independently | D Fake; real broker U |
| Drop during publish | disconnected/retry or buffered PUBACK if already received; exact failure reason may be lost | D Fake; real socket U |
| PUBACK absent | retryable unknown outcome; no invented receipt; cleanup can fail independently | D Fake; local broker U |
| Disconnect during TLS | stop request cannot interrupt handshake; join timeout retained thread | S,N |
| Shutdown while publish blocked | close may wait on wrapper/Transport locks without deadline | S; controlled blocked-connect test is NOT blocked-publish proof |
| Repeated/concurrent close | repeat retained-resource cleanup supported; successful Fake disconnect counted once | D; real socket reclamation U |

## 7. Reproducible local strategy

Existing targeted commands (not rerun in this audit):

```powershell
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests/test_paho_client.py -q -p no:cacheprovider
.\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests/test_iotda_transport.py -q -p no:cacheprovider
```

Existing test names: test_blocked_connect_reports_retained_thread_then_retry; test_concurrent_close_disposes_once; test_real_paho_stalled_tls_exposes_cleanup_limit (test_paho_client.py:40,79,92). The real network test overrides destination to 127.0.0.1 with a local listener; it is deliberately negative evidence, then releases server in finally and joins threads. Report audit/c22-lifecycle-verified-20261107.xml is the latest 187-pass result.

Planned harness, not implemented by this audit:
- DNS: deterministic injected resolver barrier with controlled release. Assert close does not falsely report disposal; always release in finally. OS resolver hangs cannot safely be induced indefinitely in the main test process.
- TCP: local refusal and controlled multi-address connector; distinguish per-address timeouts from total budget. Avoid internet blackhole tests.
- TLS: ephemeral local CA/server fixtures covering valid chain, untrusted chain, wrong hostname, handshake stall. Confirm actual sockets and all threads close; timing tolerances are OS measurements, not hard real-time proofs.
- MQTT: minimal local TLS broker emits success/rejected/no CONNACK and success/missing PUBACK; test backpressure/partial DISCONNECT and peer-held sockets. Verify descriptor/socketpair accounting, not just Thread.is_alive.
- Concurrent shutdown: blocked publish and disconnect with controllable barriers, multiple close callers, callbacks raising, late PUBACK plus cleanup failure. Every test checks delivery outcome separately from cleanup result and has finite test-owned release paths.
- A watchdog or isolated test runner, if needed to contain hang experiments, is a separate testing design; it does not approve production subprocess architecture.

No new live/fault experiments are claimed here. Do not treat expected behavior from source as already locally tested.

## 8. Can in-process Paho satisfy bounded exit?

Current implementation: NO. It has demonstrated bounded failure detection in selected paths, not bounded cancellation/reclamation.

In-process alternative: possible only under explicitly constrained assumptions and a revised lifecycle design: avoid unbounded resolver ownership, give each connection phase an owned/cancellable socket or proven finite deadline, use a single overall monotonic close budget across locks and operations, and verify actual socket release. Need to investigate a supported external event-loop path/nonblocking TLS/resolver strategy and Paho 2.1.0 extension points. This is a design proposal, not a claim that public Paho APIs already provide everything needed.

Arbitrary Python threads executing blocking resolver/backend/user callback cannot be safely force-killed. If the requirement is strict application-independent exit despite such hangs, threads alone cannot meet it. A guaranteed real-time deadline against an unresponsive OS is not achievable merely by switching architectures either; state operational assumptions.

## 9. Is process isolation necessary?

Not yet established as universally necessary. It becomes a strong candidate if hard service-level shutdown must survive uncontrolled resolver/native calls and an acceptable in-process ownership design cannot be demonstrated. It needs a SEPARATE proposal covering process ownership, IPC, timeout/escalation, kill/join verification, socket closure, secret exposure, Windows spawn behavior and at-least-once outcome ambiguity. Do not introduce a process, daemon thread or production supervisor in this audit. Keep current live adapter release blocked until architecture review selects a feasible contract.

## 10. Recommended remediation plan and acceptance

L2 design only: define shutdown SLO and assumptions; one monotonic budget for cancellation, locks, writes, drain and join; separate delivery result from cleanup status; choose in-process feasibility prototype or separate isolation proposal. Review before business code changes.

L3 lifecycle implementation after approval: explicit states NEW/CONNECTING/READY/CLOSING/CLEANUP_FAILED/CLOSED; ownership for provisional sockets, resolver work, queues and thread; cancellation wakes IO; CLOSED only after verified release. Do not solve handshake by changing MQTT keepalive or reaching into Paho private _sock without ownership review.

L4 tests: implement local matrix above; require no false disposed state, no resource-count drift, bounded caller behavior and evidence for worker/thread termination under specified assumptions. All 187 existing regressions remain required; zero skips must not hide unresolved tests. Record unresolved impossibility cases rather than relaxing assertions.

L5 downstream: only after lifecycle acceptance review Worker/provider/policy/fresh finished_at and old Mock database compatibility. Actual IoTDA is a separate isolated-device authorization/acceptance step. PUBACK, platform receive and business processing stay distinct.

Release blockers: DNS cancellation/budget; TLS handshake deadline independent of keepalive; lock-inclusive close budget; disconnect return-code and pending-write handling; socket/socketpair release evidence; lifecycle state correctness; post-CONNACK failure reporting; real local TLS/MQTT scenario coverage. No production/live factory, Worker or CLI enablement until these pass.

Audit stop: deliver this report and wait for architecture review. No implementation follows automatically.
