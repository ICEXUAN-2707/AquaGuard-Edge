# C2.2 interface revision - 2026-11-07

Implemented: validated timeout inputs; injectable monotonic clock; deadlines before start/publish; callback receipt deadline checks; bounded callback cache; phase checks; UTC validation outside state lock; cancellation wakeup; sanitized client exceptions and distinct TLS failure; cleanup failure retains the client reference and accepted PUBACK evidence on CleanupError.outcome; stopped reuse after cleanup failure.

Added IoTDAAdapter as a DeliveryAdapter-shaped authorization/mapping wrapper with request/snapshot ID consistency. Mapping JSON goes directly to transport without a second serialization. This wrapper is not registered with Worker/CLI.

Evidence: existing/new suite collected before wrapper tests: 150 passed, zero failed/skipped. Wrapper increment: 3 passed, zero failed/skipped. Reports: audit/c22-revision-20261107.xml and audit/c22-wrapper-20261107.xml. These are two runs, not a claimed single 153-test run.

Remaining release gates: explicit typed Client Protocol and topic/QoS/identity binding; granular connection reason mapping; outcome preservation for every non-accepted cleanup failure; validated bounded start/publish/close implementation; actual Paho lifecycle/official auth verification; persistent policy/fresh-clock Worker integration. Synchronous client calls are still contractual, not forcibly cancellable. Concurrent close wakes waits but cannot interrupt a blocked client call. No real Paho integration is claimed.

No live connection, business/database/Mock modification, dependency change or Git commit. Next development should resolve client contract and Paho cleanup feasibility before enabling a live entry point.
