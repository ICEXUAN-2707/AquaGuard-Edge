# C2.2 lifecycle stage closeout

Baseline a6c51af; latest work is uncommitted. This closes the audit/containment increment, NOT the formal IoTDA Adapter release.

## Implemented containment fixes

PahoClient close shares one monotonic episode deadline across cleanup lock, state-lock acquisition and thread join. Stop is signalled without waiting for the publish lock. Concurrent/repeated callers do not intentionally reset the episode budget. Backend disconnect and resource checks run in the owned network thread, not synchronously after caller join. Success requires owner cleanup complete; errors, non-success disconnect rc, retained public socket or Paho wakeup-pair references prohibit disposed=True. No GC-based disposal claim. Callback-thread close remains rejected.

Resource verification reads fixed-version Paho internals for wakeup inventory only; it does not mutate private sockets, inject preconnected sockets or change TLS verification. Public Paho APIs have not established complete wakeup-pair teardown, so real lifecycle release remains blocked, honestly.

The close deadline bounds cooperative caller waits, not arbitrary OS execution. A DNS/TLS/native call may still hold a non-daemon thread. A repeated close after deadline may observe already-completed cleanup but does not grant a fresh wait interval. Failed resource release is reported rather than silently retried from an unsafe second owner.

## Feasibility decision

Stock Paho public connection setup does not satisfy the proposed cancellable provisional-socket ownership: _create_socket returns only after blocking DNS/TLS and no reviewed public preconnected-TLS handoff was found. External-loop APIs solve protocol pumping but not this setup boundary. Do not enable the existing real factory or label this L3 architecture fully implemented.

No subprocess implementation or private connector patch was introduced. Next architectural decision is a narrowly version-pinned connector adapter proposal versus separately reviewed communication-process containment. These are alternatives, not implied approvals. Until selected and proven, Worker/CLI integration and IoTDA acceptance must remain gated.

## Tests and scope

Added tests cover retained socket, failed disconnect, publish-lock close budget and no automatic deadline renewal. Prior block/release tests now explicitly join test-owned controlled-release threads before observing final cleanup, avoiding a new hidden shutdown budget. Full suite report: audit/c22-stage-close-20261107.xml (local, not CI; no temporary databases or report included in Git).

No SQLite Schema, Worker, CLI, event/ACK, Mock, credentials or dependency changes. No cloud connection, commit or push. Unrelated user modifications preserved.

Final validation: 190 passed, 0 failed, 0 skipped in 106.31 seconds. Diff whitespace check passed. Shared budget uses existing close_timeout (default 2s); the L2 proposed 5s phase allocation is not silently enabled or claimed implemented.
