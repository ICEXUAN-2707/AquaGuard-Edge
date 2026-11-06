# C2.1 delivery boundary

Baseline: main b304174. No database migration or policy version change.

## Responsibilities

- Store._write retains atomic event, transition, outbox and immutable payload writes.
- outbox.Worker retains claim/finish, durable attempts, leases, token fencing, simulation filtering and Mock receipt validation.
- delivery.DeliveryService claims, invokes an injected adapter after the claim connection closes, then finishes using the original token.
- adapters.base defines transport-only outcomes and controlled exceptions without storage dependencies.
- adapters.mock implements all four existing CLI modes without network IO.
- run.py constructs the service and closes the adapter in finally. Worker.step remains a compatible wrapper.

## Semantics and compatibility

ACCEPTED means Mock transport acknowledgement only. send never creates a business receipt. Existing Mock business_receipt and finish compatibility remain available; no cloud receipt endpoint exists.

The delivery_policy mock-r05-v1 value, schema, defaults, retry limits and error normalization are unchanged. Missing historical payloads remain errors; latest event state is never used to reconstruct historical messages.

Unexpected adapter exceptions propagate and leave SENDING recoverable through lease expiration. Controlled temporary/permanent exceptions map to existing retry/failure handling. Adapter inputs are copies and cannot mutate persisted payloads.

Multiple workers fence the same message through SQLite transactions and durable attempts. Event versions are NOT strictly serialized: a later version may be claimed while an earlier version is SENDING or waiting to retry. This existing limitation is tested and must be resolved separately before claiming ordered real-cloud delivery.

## Validation

Baseline: 82 tests passed. Added delivery tests cover mode parity, a separate SQLite write during send, payload isolation, controlled and unexpected exceptions, source isolation, version-order limitations, main Worker compatibility and independent-process claim exclusion.

No IoTDA connection, new infrastructure, event/ACK changes, schema migration or dependency changes are included.
