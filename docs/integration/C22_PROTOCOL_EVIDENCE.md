# C2.2-C1 protocol evidence and implementation status

Retrieved: 2026-11-07. Baseline: d4d4862. No IoTDA connection or credentials used.

## Authoritative sources

- Huawei secret authentication: https://support.huaweicloud.com/devg-iothub/iot_02_0203.html
- Huawei device message API: https://support.huaweicloud.com/intl/en-us/api-iothub/iot_06_v5_3016.html
- Paho VERSION2 migration: https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html
- Paho client API: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
- Local fixed implementation: .venv-app/Lib/site-packages/paho/mqtt/client.py (2.1.0), loop_start/loop_stop and socket connection paths.

## Verified vs project policy

Authentication: Client ID consists of device ID, identity type 0, signature mode 0/1 and UTC YYYYMMDDHH timestamp separated by underscores. Username is device ID. HMAC-SHA256 uses timestamp as key and device secret as message. Implemented in adapters/iotda_auth.py with the official public dummy vector. Password is excluded from repr. Timestamp verification defaults to enabled as project policy; mode 0 is explicit.

Message API: $oc/devices/{device_id}/sys/messages/up is the documented upstream topic. System wrapper permits object_device_id/name/id/content; content can be Object or String. Direct-device object_device_id must match topic identity. Current mapping structure aligns with these documented fields; this is structural verification, not live instance acceptance or business deduplication evidence. The API's unique message ID description does not prove broker/platform deduplicates retries.

Project delivery policy remains QoS1 and retain=false. Exact instance quotas, payload limit, supported QoS and certificate chain applicability must still be verified for the selected instance before release. No universal message-size limit was invented or hardcoded.

Paho VERSION2 uses normalized reason codes; legacy MQTT3 CONNACK integers cannot be interpreted as VERSION2 values. Added pure connect_reason/publish_succeeded translation. Intended boundary is ReasonCode.value, not ReasonCode truthiness. MQTT3.1.1 PUBACK has no MQTT5 negative reason field; normalization does not imply those platform features exist.

## Lifecycle gate

Local loop_start creates a daemon network thread. loop_stop sets termination and calls thread.join without a timeout. socket.create_connection receives connect_timeout, but that does not establish a hard DNS deadline. Therefore connect_async plus Event.wait plus loop_stop is NOT proven bounded cancellation. No production Paho wrapper or live factory is added in this increment. This follows the agreed release gate rather than masking resource risks with another daemon thread.

Before wrapper implementation is accepted: demonstrate an owned in-process network lifecycle that exits under DNS/TCP/TLS failures using a local fault harness, or separately review a managed-process design. Neither option is silently selected here. Fake tests prove contracts only. Worker/provider/policy/fresh finish time integration remains separate.

## Added files and tests

adapters/iotda_auth.py: credential derivation with UTC conversion and input validation.
adapters/paho_reasons.py: normalized reason classification.
tests/test_iotda_auth.py: public official HMAC vector, UTC mode, invalid input, reason categories and publish values.

No changes to business events, ACK, Schema, Mock, Worker or CLI. No dependency installation, Git commit or push.
