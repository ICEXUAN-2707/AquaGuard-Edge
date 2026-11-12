"""Local crash harness. Never used by Worker or CLI."""
import os
import sys
from experiments.process_probe import ProcessProbe


if __name__ == "__main__":
    probe = ProcessProbe(message_id="parent-death", attempt_token="local",
                         mode="result_then_stall")
    probe.start()
    if probe.wait_result(10) is None:
        probe.close()
        raise SystemExit(2)
    print(probe.process.pid, flush=True)
    # Wait for the test's crash command after demonstrating child readiness.
    sys.stdin.readline()
    os._exit(23)
