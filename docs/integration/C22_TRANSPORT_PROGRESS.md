# C2.2 offline transport increment - 2026-11-07

Baseline: d5548b7 plus uncommitted B1 config/mapping. This increment is authorized by the subsequent request to plan and develop the next stage.

Implemented adapters/iotda_transport.py with an injected client contract and tests/test_iotda_transport.py. No Paho factory, credentials, authorization bypass, real network entry, Worker integration or CLI integration exists.

The injected client must provide nonblocking start/publish and bounded close. The core serializes sends, captures generation/MID callbacks before publish returns, waits for matching acknowledgements, classifies controlled failures and disposes each attempt generation. This deliberately uses one client per attempt for isolation rather than connection reuse. close failure stops reuse. UTC callback timestamps record receipt time; waits use Python event/monotonic deadlines.

This is NOT a released IoTDA Adapter and does not implement DeliveryAdapter.send(request). The future wrapper must authorize and map snapshots, establish TLS/authentication, validate client identity, provide real bounded lifecycle behavior and return transport evidence to fresh-clock finish handling. Fake tests prove core sequencing only, not Paho thread cleanup or platform compatibility.

Next tasks:
1. Review B1 config/mapping and this injected-client contract.
2. Verify official authentication/envelope/limits and inspect fixed Paho 2.1.0 lifecycle.
3. Implement and test the Paho wrapper, including DNS/TCP/TLS shutdown feasibility. Do not hide blocked threads behind daemon timeout.
4. Review policy persistence and backward-compatible clock/provider integration separately.
5. Explicitly authorize isolated test-device connection only after offline acceptance.

No Git commit, actual IoTDA connection, dependency/schema/Mock/ACK changes in this increment. Outstanding ordering and cloud business receipt work remains C2.3/C2.4.
