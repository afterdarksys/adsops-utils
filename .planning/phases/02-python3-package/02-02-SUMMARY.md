---
phase: 02-python3-package
plan: 02
subsystem: infractl
tags: [python, asyncssh, typer, docker, k3s, pytest, parallel-ssh]

# Dependency graph
requires:
  - phase: 02-python3-package
    plan: 01
    provides: "adsops package scaffolding, cli.py conditional imports, asyncssh installed"
provides:
  - "adsops infractl docker ls/start/stop/restart/logs/exec over SSH"
  - "adsops infractl k3s nodes/pods/logs/apply over SSH"
  - "Multi-host parallel execution via asyncio.gather() (D-07)"
  - "asyncssh connection layer with SSH_AUTH_SOCK guard"
  - "Input validation: hostname and container name allowlist patterns (T-02-05)"
  - "k3s apply with asyncssh.scp + basename path guard (T-02-06)"
  - "17 unit tests with mocked asyncssh"
affects: [02-03, 03-systemapi-agent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncssh.connect() used as async context manager — mock must return MagicMock (not AsyncMock) with __aenter__/__aexit__ as AsyncMocks"
    - "run_parallel_sync uses asyncio.gather(return_exceptions=True) — failed hosts return Exception, not raised (T-02-08)"
    - "CLI docker ls / k3s nodes/pods use run_parallel_sync for multi-host execution (D-07)"
    - "logs/exec/k3s_logs commands use stream_command() for line-by-line output"
    - "k3s_apply: asyncssh.scp within async with connect() block; os.path.basename() prevents remote path traversal (T-02-06)"
    - "Input validation with re.compile allowlist patterns applied before SSH command construction (T-02-05)"

key-files:
  created:
    - tools/adsops/src/adsops/infractl/__init__.py
    - tools/adsops/src/adsops/infractl/ssh.py
    - tools/adsops/src/adsops/infractl/docker.py
    - tools/adsops/src/adsops/infractl/k3s.py
    - tools/adsops/src/adsops/infractl/cli.py
    - tools/adsops/tests/test_infractl.py
  modified: []

key-decisions:
  - "asyncssh mock fixture uses MagicMock(return_value=cm) for connect() where cm has AsyncMock __aenter__/__aexit__ — AsyncMock for connect() itself breaks async-with protocol because Python does not await connect() before calling __aenter__"
  - "Input validation added for hostnames and container names via re.compile allowlists (T-02-05 mitigation — not in original plan spec but required by threat model)"
  - "k3s_pods defaults to -A (all namespaces) matching Go infractl behavior when ns is 'all' or empty"

# Metrics
duration: 4min
completed: 2026-05-04
---

# Phase 2 Plan 02: infractl Module Summary

**asyncssh-based infractl module: remote Docker and k3s management over SSH with multi-host parallel execution, SSH agent auth guard, input validation, and 17 passing unit tests**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-04T09:21:39Z
- **Completed:** 2026-05-04
- **Tasks:** 2
- **Files created:** 6 new files

## Accomplishments

- `adsops infractl docker ls/start/stop/restart/logs/exec` — Docker commands executed over SSH
- `adsops infractl k3s nodes/pods/logs/apply` — k3s/kubectl commands over SSH
- Multi-host parallel execution: `adsops infractl docker ls host1 host2` runs via `asyncio.gather()` with `return_exceptions=True`
- SSH agent guard in `ssh.py` — raises `RuntimeError` with clear message when `SSH_AUTH_SOCK` unset
- k3s apply: SCPs manifest to `/tmp/adsops-manifest-{basename}` then runs kubectl apply/delete and cleanup
- Input validation: hostnames and container names validated against allowlist patterns before SSH command composition
- Auto-registered on root `adsops` CLI via existing conditional import in `cli.py`
- 17 unit tests all pass with mocked asyncssh

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | asyncssh connection layer and infractl service modules | cfcf1b5 | infractl/__init__.py, ssh.py, docker.py, k3s.py |
| 2 | infractl CLI and unit tests | cd4b0c7 | infractl/cli.py, tests/test_infractl.py |

## Files Created/Modified

- `tools/adsops/src/adsops/infractl/__init__.py` - Empty package marker
- `tools/adsops/src/adsops/infractl/ssh.py` - run_command/stream_command/run_parallel/run_sync/run_parallel_sync with SSH_AUTH_SOCK guard
- `tools/adsops/src/adsops/infractl/docker.py` - docker_ls/start/stop/restart/logs/exec with hostname/container name validation
- `tools/adsops/src/adsops/infractl/k3s.py` - k3s_nodes/pods/logs/apply with asyncssh.scp and path guard
- `tools/adsops/src/adsops/infractl/cli.py` - Typer sub-app with docker and k3s command groups (6 docker + 4 k3s commands)
- `tools/adsops/tests/test_infractl.py` - 17 unit tests (mocked asyncssh, agent guard, input validation, CLI routing)

## Decisions Made

- **asyncssh mock pattern:** `asyncssh.connect()` is used as `async with asyncssh.connect(...) as conn:`. Python does NOT await `connect()` before calling `__aenter__`. The correct mock is `MagicMock(return_value=cm)` where `cm.__aenter__ = AsyncMock(return_value=conn)`. Using `AsyncMock` for `connect()` makes it return a coroutine that lacks `__aenter__`, causing `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`.
- **Input validation added (Rule 2):** The threat model (T-02-05) requires validating container names contain only `[a-zA-Z0-9_.-]`. Implemented `_validate_host()` and `_validate_name()` with compiled regex allowlists in `docker.py`. Applied before every SSH command construction.
- **k3s_pods default:** Defaults to `-A` (all namespaces) when `ns="all"` or empty, matching Go infractl behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed asyncssh mock fixture for async context manager protocol**
- **Found during:** Task 2 (test execution — 9 failures)
- **Issue:** Plan template showed `mock.connect = AsyncMock(return_value=conn)`. When `run_command()` uses `async with asyncssh.connect(host, known_hosts=None) as conn:`, Python calls `connect()` synchronously then calls `__aenter__` on the return value. `AsyncMock(return_value=conn)` makes `connect()` return a coroutine, not an async context manager — raising `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`.
- **Fix:** Changed fixture to `mock_module.connect = MagicMock(return_value=cm)` where `cm` is a `MagicMock` with `cm.__aenter__ = AsyncMock(return_value=conn)` and `cm.__aexit__ = AsyncMock(return_value=False)`.
- **Files modified:** tools/adsops/tests/test_infractl.py
- **Verification:** All 17 tests pass
- **Committed in:** cd4b0c7 (Task 2 commit)

**2. [Rule 2 - Missing Critical Functionality] Added hostname and container name input validation**
- **Found during:** Task 1 (threat model review — T-02-05 mitigate disposition)
- **Issue:** T-02-05 requires container names to be validated with `[a-zA-Z0-9_.-]` allowlist. Plan action text mentioned this but did not include it in the code snippets.
- **Fix:** Added `_SAFE_HOST_RE` and `_SAFE_NAME_RE` compiled regex patterns and `_validate_host()`/`_validate_name()` functions called before every SSH command in `docker.py`. Added 2 test cases (`test_docker_invalid_container_name_rejected`, `test_docker_invalid_host_rejected`) verifying injection is rejected.
- **Files modified:** tools/adsops/src/adsops/infractl/docker.py, tools/adsops/tests/test_infractl.py
- **Verification:** Validation tests pass; injection strings raise `ValueError`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical functionality from threat model)
**Impact on plan:** Both fixes necessary for correctness and security. No scope creep.

## Known Stubs

None — all commands are fully wired through to asyncssh execution.

## Threat Surface Scan

All threat model mitigations implemented:
- T-02-05 (Tampering/docker.py): Hostname and container name validated with allowlist regex before SSH command composition
- T-02-06 (Tampering/k3s apply): `os.path.basename(local_file)` used for remote `/tmp` path to prevent directory traversal
- T-02-07 (Spoofing/ssh.py): `known_hosts=None` — accepted; documented in code comments as intentional for internal tooling
- T-02-08 (DoS/ssh.py): `asyncio.gather(return_exceptions=True)` — failed hosts return `Exception` objects, do not block parallel execution

No new network endpoints or auth paths beyond what the plan specified.

## Self-Check: PASSED

Files verified:
- FOUND: tools/adsops/src/adsops/infractl/__init__.py
- FOUND: tools/adsops/src/adsops/infractl/ssh.py
- FOUND: tools/adsops/src/adsops/infractl/docker.py
- FOUND: tools/adsops/src/adsops/infractl/k3s.py
- FOUND: tools/adsops/src/adsops/infractl/cli.py
- FOUND: tools/adsops/tests/test_infractl.py

Commits verified:
- FOUND: cfcf1b5 (Task 1)
- FOUND: cd4b0c7 (Task 2)

Tests: 17 passed, 0 failed

---
*Phase: 02-python3-package*
*Completed: 2026-05-04*
