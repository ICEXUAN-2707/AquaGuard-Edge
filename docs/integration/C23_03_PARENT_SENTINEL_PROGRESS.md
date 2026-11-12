# C23-03 parent sentinel experiment

Date: 2026-11-10. Local-only, isolated `.c23-process` checkout.

Added a daemon sentinel monitor before the spawn child begins network work. When
the multiprocessing parent sentinel signals, the child exits with code 72. The
monitor performs no result-channel reads or writes and does not own delivery
accounting. Existing explicit close retains its original deadline and ownership.

Added a subprocess crash harness: a child first emits its synthetic result and
then stalls; its parent calls `os._exit(23)` without cleanup. The Windows test
checks child exit using a process handle, or error 87 if the PID already vanished.
The latter branch is PID-based evidence, not retained-handle identity proof.

This is runtime-level mitigation, not an OS-enforced containment policy. A child
that cannot schedule Python threads may survive; descendants are not contained.
Windows Job Object policy, startup cancellation and startup/crash race evidence
remain open. No production supervisor/Worker integration or cloud acceptance.

An initial selected-file test run failed collection because the existing tests
depend on another module establishing the experiments import path. No tests ran
in that attempt (`audit/c23-parent-death-01.xml`). Full-directory regression is
the supported command for this increment.

Verification command:

```powershell
..\.venv-app\Scripts\python.exe -m pytest spikes/C-business/tests spikes/SP-06/tests tests/contracts tests/smoke -q -p no:cacheprovider --basetemp audit/c23-regression-03 --junitxml audit/c23-regression-03.xml
```

Result: 264 passed in 65.17s, exit 0. Includes prior 263-case scope and the new
parent-death case; counts overlap and must not be added. `git diff --check`
passed. New untracked files were also inspected. No independent review, cloud
connection, dependency installation, commit or push was performed.
