# C2.2-C2 Paho injection-only increment

Implemented adapters/paho_client.py and tests/test_paho_client.py. No live factory or Worker/CLI registration. Client construction requires an explicitly supplied factory. Tests include real Paho construction, Fake lifecycle cases and a real loopback TCP/TLS-stall harness; no IoTDA access.

Binding: verified credential helper supplies Client ID/username/password. Factory requests VERSION2, MQTTv311 and reconnect_on_failure=False. SSLContext requires CA and hostname validation. Topic is fixed to the configured cloud device; publish passes payload unchanged, QoS1, retain=false. VERSION2 callbacks use normalized reason helpers.

Lifecycle experiment: own non-daemon thread calls connect and pumps client.loop; loop_start/loop_stop are not used. close signals stop and joins with a timeout. A blocked fake connect results in IOTDA_THREAD_EXIT_TIMEOUT; thread reference remains owned, publishing is disabled and retry close succeeds after controlled release. Successful loop exits are joined. No daemon timeout is claimed as cancellation.

Release restrictions: this is not proven bounded real network cleanup. DNS/TCP/TLS may leave the owned thread alive; disconnect itself has not been proven bounded. A loopback TLS-stall harness has now run and confirms cleanup can time out while handshake remains blocked. Background connection exceptions are classified; concurrent close is serialized and tested. Post-CONNACK failures, callback fault behavior, DNS and normal trusted TLS sessions still need further validation. close must not be invoked synchronously from its own callback.

Next: extend the local socket/TLS harness to failed trust, normal sessions and refused TCP, then resolve DNS and bounded shutdown. Only after resource exit evidence decide whether an in-process lifecycle is sufficient or review process isolation. Keep real IoTDA, Worker policy/provider/fresh finish time and database integration gated separately.

The prior protocol review did not establish instance-specific payload/rate limits or live mapping acceptance. No schema, event, ACK, Mock, dependency or credentials changes. No commit/push in this increment.
