---
phase: 03-systemapi-agent-improvements
plan: 01
subsystem: infra
tags: [go, starlark, sysscript, docker, k3s, entitlements, security]

# Dependency graph
requires:
  - phase: 02-python3-package
    provides: "Phase 2 complete; systemapi-agent baseline confirmed"
provides:
  - "Entitlements struct with AllowContainers and AllowK3s bool fields"
  - "SysscriptEngine with dockerClient and k3sClient fields"
  - "Conditional buildSysModule() — containers/k3s absent when not entitled"
  - "Thread.Load in Execute() with path traversal protection (T-03-01)"
  - "DockerClient stub (baseURL field for test injection)"
  - "K3sClient stub (TLS from kubeconfig, base64 cert decoding)"
  - "Tests: entitlement enforcement + Thread.Load path traversal/file-not-found"
affects: [03-02, 03-03, 03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Entitlement-conditional namespace: containers/k3s keys omitted from sysDict when disabled"
    - "Thread.Load with filepath.Clean + HasPrefix path traversal guard"
    - "Client lazy init: DockerClient/K3sClient only created when entitlement granted"
    - "Test engine construction bypasses NewSysscriptEngine to avoid live Docker/k3s connections"

key-files:
  created:
    - systemapi-agent/docker_client.go
    - systemapi-agent/k3s_client.go
    - systemapi-agent/sysscript_test.go
  modified:
    - systemapi-agent/sysscript.go

key-decisions:
  - "Placeholder method stubs added to sysscript.go for containersList/Stats/Stop/Start/Restart + k3sNodes/Pods/Apply — replaced by Plans 02/03"
  - "Starlark error messages use 'attribute' not 'field'; test assertions corrected from plan spec"
  - "type(sys.containers) returns 'struct' not 'containers' in Starlark; presence tests check for no error instead"

patterns-established:
  - "buildSysModule conditionally adds namespaces: check engine.Entitlements.AllowX before sysDict assignment"
  - "Thread.Load cache pattern with loadFn closure; sub-threads inherit Load to support nested load() calls"

requirements-completed: [AGENT-06]

# Metrics
duration: 18min
completed: 2026-05-04
---

# Phase 3 Plan 01: Entitlements + Client Stubs + Thread.Load Summary

**Entitlement-gated sys.containers/sys.k3s with Thread.Load path-traversal protection and DockerClient/K3sClient stubs — structural skeleton for Plans 02-04**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-04T14:30:00Z
- **Completed:** 2026-05-04T14:48:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- DockerClient (baseURL for test injection, DOCKER_HOST env, Unix socket transport) and K3sClient (TLS from kubeconfig, base64 cert decoding, D-04 path resolution) stubs created
- sysscript.go updated with AllowContainers/AllowK3s entitlement fields, conditional buildSysModule(), Thread.Load with T-03-01 path traversal protection
- All entitlement enforcement and Thread.Load tests pass (6 tests, 1 skipped in short mode)

## Task Commits

Each task was committed atomically in the systemapi.io repo:

1. **Task 1: Client type stubs with baseURL for test injection** - `6e56a25` (feat)
2. **Task 2: Entitlements, buildSysModule conditionals, Thread.Load, SysscriptEngine fields** - `385ec15` (feat)
3. **Task 3: Tests for entitlement enforcement and Thread.Load** - `3050705` (test)

**Plan metadata:** (committed below)

## Files Created/Modified
- `systemapi-agent/docker_client.go` - DockerClient struct with Unix socket transport, DOCKER_HOST env support, baseURL for test injection
- `systemapi-agent/k3s_client.go` - K3sClient struct with TLS from kubeconfig, base64 cert decoding
- `systemapi-agent/sysscript.go` - Entitlements struct extended, SysscriptEngine fields added, Execute() Thread.Load wired, buildSysModule() conditional containers/k3s, placeholder stubs
- `systemapi-agent/sysscript_test.go` - 7 tests: 4 entitlement tests (containers/k3s absent/present), 2 Thread.Load tests (path traversal, file not found), 1 skipped (success, needs /etc/systemapi/scripts/)

## Decisions Made
- Placeholder method stubs for containers/k3s methods added to sysscript.go bottom — will be deleted and replaced by real implementations in Plans 02/03 (methods on a type can span files in the same package)
- `containersRun` from sys_advanced.go left in place (it still compiles; Plan 02 will supersede it when sys_containers.go is created)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected Starlark error message assertions in sysscript_test.go**
- **Found during:** Task 3 (Tests for entitlement enforcement)
- **Issue:** Plan specified error should contain `"has no .containers field"` but actual Starlark error is `"has no .containers attribute"`. Plan also specified `type(sys.containers)` should contain `"containers"` but Starlark's `type()` returns the generic `"struct"` string.
- **Fix:** Changed assertions to `"has no .containers"` (drops "field" suffix), and changed presence tests to check for no error rather than output content
- **Files modified:** systemapi-agent/sysscript_test.go
- **Verification:** All 6 non-skipped tests pass
- **Committed in:** 3050705 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: incorrect test assertions)
**Impact on plan:** Necessary for test correctness. Plan's expected error strings didn't match actual Starlark runtime messages. No scope creep.

## Issues Encountered
None beyond the test assertion mismatch documented above.

## Known Stubs
The following placeholder stubs exist in sysscript.go and are intentional — replaced by Plans 02/03:
- `containersList`, `containersStats`, `containersStop`, `containersStart`, `containersRestart` (bottom of sysscript.go) — replaced by sys_containers.go in Plan 02
- `k3sNodes`, `k3sPods`, `k3sApply` (bottom of sysscript.go) — replaced by sys_k3s.go in Plan 03

## Next Phase Readiness
- Plan 02 can now create sys_containers.go with real Docker API methods — the DockerClient stub and containersList/etc method stubs are ready to be replaced
- Plan 03 can create sys_k3s.go with real Kubernetes API methods — the K3sClient stub and k3sNodes/etc stubs are ready
- Plan 04 can reference the Entitlements struct fields (AllowContainers/AllowK3s) for telemetry alignment

---
*Phase: 03-systemapi-agent-improvements*
*Completed: 2026-05-04*
