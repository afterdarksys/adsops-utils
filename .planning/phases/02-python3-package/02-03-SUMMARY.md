---
phase: 02-python3-package
plan: 03
subsystem: stats
tags: [python, psutil, aiohttp, protobuf, typer, pytest, mocksys, starlark]

# Dependency graph
requires:
  - phase: 02-python3-package
    plan: 01
    provides: "adsops package scaffolding, cli.py conditional imports, output.py"
  - phase: 02-python3-package
    plan: 02
    provides: "infractl module wired; asyncssh pattern established"
provides:
  - "adsops stats once — psutil-based local metrics via StatsSnapshot proto"
  - "adsops stats fetch <host> — aiohttp fetch from statsagent /stats returning TelemetryPayload"
  - "MockSys class with all 15 namespaces (14 verified sysscript.go + k3s stub)"
  - "MockNamespace fixture-driven dispatch for Starlark sys global replacement"
  - "test_cli.py: 6 PY-05 CLI routing tests validating hostctl/infractl/stats wiring"
  - "Full test suite: 49 tests, 0 failures across all 4 test files"
affects: [03-systemapi-agent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "psutil.cpu_percent(interval=1) blocks 1s max — safe for CLI invocation (T-02-11)"
    - "OSError/PermissionError caught in disk_partitions loop to skip inaccessible mounts"
    - "asyncio.run(_fetch()) wraps aiohttp coroutine from sync Typer command (D-06 pattern)"
    - "protobuf json_format.Parse() validates statsagent JSON response field types (T-02-09)"
    - "aiohttp.ClientTimeout(total=10) prevents hung connections to statsagent (T-02-09)"
    - "MockNamespace.__getattr__ returns callable that raises NotImplementedError when fixture missing"
    - "MockSys fixtures dict keyed by 'namespace.method' — callables receive args, non-callables returned directly"

key-files:
  created:
    - tools/adsops/src/adsops/stats/__init__.py
    - tools/adsops/src/adsops/stats/local.py
    - tools/adsops/src/adsops/stats/remote.py
    - tools/adsops/src/adsops/stats/cli.py
    - tools/adsops/src/adsops/sysscript/__init__.py
    - tools/adsops/src/adsops/sysscript/mock.py
    - tools/adsops/tests/test_stats.py
    - tools/adsops/tests/test_mocksys.py
    - tools/adsops/tests/test_cli.py
  modified: []

key-decisions:
  - "stats/remote.py uses asyncio.run(_fetch()) per D-06 — sync wrapper for Typer CLI with aiohttp async internals"
  - "MockSys fixtures keyed by 'namespace.method' string — allows independent fixture sets per namespace and enables callables that receive all args transparently"
  - "test_stats.py uses real psutil for local collector tests (no mocking needed — intentionally exercises real system) and mocked aiohttp for remote fetch test"
  - "No cli.py modification needed — existing conditional try/except block for stats_app was already in place from Plan 01"

patterns-established:
  - "Pattern: aiohttp mock uses MagicMock for session/response context managers with AsyncMock __aenter__/__aexit__ — same protocol as asyncssh mock pattern from Plan 02"
  - "Pattern: MockSys fixtures dict shared across all 15 namespaces — single dict passed to all MockNamespace instances; keys are 'ns.method' strings"

requirements-completed: [PY-04, PY-05, PY-06, PY-07]

# Metrics
duration: 3min
completed: 2026-05-04
---

# Phase 2 Plan 03: Stats Module, MockSys Harness, and CLI Routing Tests Summary

**psutil stats collection (local/remote), MockSys with 15 fixture-backed namespaces for .star testing, and PY-05 CLI routing tests — 49 tests, 0 failures**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T~09:28Z
- **Completed:** 2026-05-04
- **Tasks:** 2
- **Files created:** 9 new files

## Accomplishments

- `adsops stats once` collects CPU/mem/disk/network/process metrics via psutil, returns StatsSnapshot proto
- `adsops stats fetch <host>` fetches TelemetryPayload from statsagent `/stats` endpoint over aiohttp with 10s timeout and protobuf field validation
- `MockSys` provides all 15 namespaces (14 verified from sysscript.go + k3s forward-compat stub) with fixture-driven dispatch for Starlark script testing
- `test_cli.py` proves PY-05: `adsops --help` shows hostctl, infractl, and stats; each subcommand help lists expected commands
- Full suite: 49 tests across test_hostctl.py, test_infractl.py, test_stats.py, test_mocksys.py, test_cli.py — all pass

## Task Commits

1. **Task 1: stats module — local collector, remote fetch, CLI** - `d6f8fd0` (feat)
2. **Task 2: MockSys harness, CLI routing tests (PY-05)** - `03fcf14` (feat)

## Files Created/Modified

- `tools/adsops/src/adsops/stats/__init__.py` - Empty package marker
- `tools/adsops/src/adsops/stats/local.py` - collect_once() via psutil returning StatsSnapshot proto
- `tools/adsops/src/adsops/stats/remote.py` - fetch_once() via aiohttp from statsagent /stats endpoint
- `tools/adsops/src/adsops/stats/cli.py` - Typer sub-app with 'once' and 'fetch' commands
- `tools/adsops/src/adsops/sysscript/__init__.py` - Empty package marker
- `tools/adsops/src/adsops/sysscript/mock.py` - MockSys + MockNamespace with all 15 namespaces
- `tools/adsops/tests/test_stats.py` - 5 unit tests (real psutil + mocked aiohttp)
- `tools/adsops/tests/test_mocksys.py` - 7 unit tests covering D-08/D-09/D-10
- `tools/adsops/tests/test_cli.py` - 6 PY-05 CLI routing tests

## Decisions Made

- Used `asyncio.run(_fetch())` in remote.py per the established D-06 pattern from Plan 01 (asyncssh probe). Keeps CLI sync while using aiohttp async internally.
- No modification to `cli.py` was needed — the conditional try/except block for `stats_app` was already wired in Plan 01, so creating `stats/cli.py` was sufficient for it to register automatically.
- Real psutil used for local collector tests — mocking psutil would test the mock, not the integration. Three tests exercise real system data.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `adsops` package was installed pointing at the main repo path, not the worktree. Reinstalled with `pip install -e` pointing at the worktree path. Tests passed immediately after.

## Known Stubs

None — all commands are fully wired through to real implementations.

## Threat Surface Scan

All threat model mitigations implemented:
- T-02-09 (Tampering/remote.py): `json_format.Parse()` validates response field types; `aiohttp.ClientTimeout(total=10)` prevents hung connections
- T-02-10 (Information Disclosure/local.py): Accepted — local stats expose system metrics intentionally for internal ops use
- T-02-11 (DoS/local.py): `psutil.cpu_percent(interval=1)` limits to 1s max; `OSError`/`PermissionError` caught in `disk_partitions` loop

No new network endpoints or auth paths beyond what the plan specified.

## User Setup Required

None — no external service configuration required. Stats fetch requires a running statsagent on the target host (existing tool, not new configuration).

## Next Phase Readiness

- PY-01 through PY-07 fully satisfied across Plans 01-03
- Phase 2 (Python3 package) is complete: hostctl, infractl, and stats modules all functional with CLI parity
- MockSys ready for use in Starlark script unit tests in Phase 3+
- Phase 3 (systemapi-agent) can proceed: sys.containers and sys.k3s stubs need real implementations

---
*Phase: 02-python3-package*
*Completed: 2026-05-04*
