# Lifecycle development and project progress - 2026-11-07

Implemented in this increment: typed background TLS/connect-timeout/network classification; core preserves those reasons despite the following disconnect notification; serialized idempotent close; tracked disposed state. Tests add background fault categories, concurrent cleanup and a real Paho connection to a loopback TCP server that stalls TLS negotiation. No IoTDA access, real credentials or dependency changes.

The first local test failed because its listening server timed out while configuration/CA initialization ran. Corrected harness order starts the server thread after client construction. This was a test timing issue, not evidence of network lifecycle success; final suite result is recorded separately.

Evidence boundaries: real stalled local TLS proves cleanup timeout retains thread ownership and later server release permits join; it disproves the assumed handshake bound. It does not prove DNS cancellation, every TCP failure path, invalid-CA handshake, normal TLS/MQTT session cleanup or disconnect's boundedness. Fake tests cover classification and concurrency, not real network behavior. Production/live release remains gated.

Project status: C2.1 delivered (d5548b7); initial offline C2.2 pushed (32dd15d); C0 fixes committed locally (d4d4862). C1 auth/reason helpers, candidate Paho wrapper and this lifecycle increment are included in the current submission. No Worker/CLI/provider/fresh finish-time integration. No real business Outbox-to-IoTDA acceptance, cloud consumer/business receipt or contact notification acceptance.

Next: local trusted/untrusted TLS fixtures and TCP refusal; typed post-CONNACK network failure propagation; callback-failure behavior; DNS/shutdown design. Then review client-policy binding and Worker compatibility separately. Do not bypass unresolved cleanup by enabling a live factory.

## Actual local TLS finding

The initial real test disproved the assumed handshake bound: Paho 2.1.0 _ssl_wrap_socket sets timeout to _keepalive before do_handshake. Therefore connect_timeout does not bound TLS handshake here. Revised test intentionally asserts close timeout retains the live thread, releases the local server, then verifies classified TLS/network failure and successful joined cleanup (Windows may report TCP reset when the server closes unread handshake bytes). This is negative release evidence, not proof of bounded shutdown. No private Paho override or keepalive distortion was introduced.

## Final regression and next milestone

Verified local JUnit audit/c22-lifecycle-verified-20261107.xml: 187 passed, zero failures/errors/skips, wall time 67.69 seconds. Source is unchanged since that successful run; documentation wording was reconciled before submission. XML and temporary databases are excluded from Git.

Next milestone: (1) decide a bounded network-resource lifecycle without daemon masking, supported by DNS/TCP/TLS fault evidence; (2) complete trusted/untrusted local TLS and callback failure tests; (3) review persistent policy/provider/fresh finish-time compatibility and old Mock DB copies; (4) only then isolated IoTDA acceptance with separate transport/platform/business evidence. No live entry point before lifecycle gate is passed.
