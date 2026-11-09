# C2.2-B1 implementation report

Baseline: d5548b7. Scope: independent offline configuration and mapping only.

## Files

- spikes/C-business/cloud_config.py: frozen configuration and test authorization bindings, environment loader, CA parsing, required TLS validation, controlled errors and secret redaction.
- spikes/C-business/cloud_mapping.py: pure immutable-snapshot validation, lineage checks, authorization and deterministic candidate JSON envelope.
- spikes/C-business/tests/test_cloud_modules.py: 37 offline test cases.
- This report. C22_IOTDA_ADAPTER_DESIGN.md remains the uncommitted design reference.

## Test evidence

Command: .venv-app/Scripts/python.exe -m pytest spikes/C-business/tests -q -ra -p no:cacheprovider --basetemp audit/c22-b1-20261106 --junitxml=audit/c22-b1-20261106.xml
Result: 131 passed, 0 failed, 0 skipped in 42.04 seconds: original 94 plus 37 new cases.
JUnit: audit/c22-b1-20261106.xml. Temporary databases are under the isolated test directory, not application data.

New coverage: normal/missing config, invalid ports/endpoints/timeouts, missing/invalid PEM CA, repr/error/output secret handling, unauthorized devices/origins, valid mapping, null/invalid DTO, mismatched lineage, stable IDs and versions, repeated mapping equality and unchanged input.
CA parsing tests use the existing local pip certificate bundle; no CA or credentials are downloaded and no dependencies installed. No fake MQTT is necessary because these two modules contain no MQTT operations.

## Decisions and differences from the broader design

1. Only two modules are implemented. No adapter, CLI, policy persistence, Worker, Outbox, Store, API, event or SQLite schema changes.
2. Environmental configuration uses AQUAGUARD_IOTDA_ENDPOINT, PORT (8883), CA_FILE, DEVICE_ID, DEVICE_SECRET, CONNECT_TIMEOUT (5), PUBACK_TIMEOUT (10), BINDINGS_FILE. PUBACK_TIMEOUT populates the publish_timeout field; it is not duplicated under another ambiguous environment name.
3. The bindings JSON has environment=test and a bindings list. Each binding contains local_device_id, cloud_device_id, authorization_class and allowed_origins. test_hardware authorizes hardware; simulation_test authorizes simulation. Both require an explicit mapping to the configured cloud device. mixed/unknown and production configuration are refused. This does not authorize historical Outbox records or CLI delivery; runtime channel binding remains unimplemented.
4. Environment variables may be populated by an operator's ignored local file; this module does not auto-load dotenv or add dependencies. BINDINGS_FILE is explicitly provided; keep local credentials/files outside Git. No new secret file was created.
5. TLS context always sets CERT_REQUIRED and check_hostname=True. There is no disable option. CA contents are validated before configuration succeeds.
6. Configuration/mapping modules emit no logs. repr excludes device_secret; errors omit supplied values; redact() masks the configured secret in caller messages. Future adapter logging must also redact derived credentials; that layer does not exist here.
7. Snapshot schema is exactly schema_version/message_id/event/transition, matching Store's immutable payload. Public DTO validation and event/transition lineage checks are mandatory. No current Event lookup occurs. MID and attempt tokens are not accepted snapshot fields.
8. Cloud wrapper remains a candidate, not a verified IoTDA wire contract. Message-size limits, official authentication/wrapper checks, live-test switch and connection/CONNACK lifecycle are deferred to their actual adapter/integration stages. No invented platform size limit.

## Remaining boundaries

Configuration validates declared test authorization, not physical route isolation. It does not send anything. Untrusted sensors cannot establish their own authorization. Runtime policy binding and historical-message protection are required before connecting it to Worker.

No Git commit, cloud connection, credential storage, business behavior change or dependency change was performed. Stop for review after B1.
