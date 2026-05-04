---
phase: 03-systemapi-agent-improvements
plan: 02
subsystem: infra
tags: [go, starlark, docker, sysscript, testing, security]

# Dependency graph
requires:
  - phase: 03-systemapi-agent-improvements
    plan: 01
    provides: "DockerClient stub with baseURL field, container method stubs in sysscript.go, Entitlements.AllowContainers"
provides:
  - "DockerClient with ListContainers, GetContainerStats, StartContainer, StopContainer, RestartContainer"
  - "isValidContainerID() with path-injection prevention (T-03-06)"
  - "GetContainerStats uses stream=false (T-03-07)"
  - "sys_containers.go: all 5 Starlark builtins for sys.containers namespace"
  - "D-02: containersList returns empty list on Docker unavailability"
  - "sys_containers_test.go: 9 tests with httptest.Server mock via baseURL injection"
affects: [03-03, 03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httptest.Server injected via DockerClient.baseURL for unit testing Docker API calls"
    - "CPU%: (cpuDelta/sysDelta)*onlineCPUs*100 with division-by-zero guards"
    - "D-02: log + return empty list on Docker unavailability (never propagate to Starlark)"
    - "containerActionResult helper: {success, error} dict following sys_config.go pattern"
    - "starlarkstruct.FromStringDict for typed container/stats return values"

key-files:
  created:
    - systemapi-agent/sys_containers.go
    - systemapi-agent/sys_containers_test.go
  modified:
    - systemapi-agent/docker_client.go
    - systemapi-agent/sysscript.go

key-decisions:
  - "doContainerPost helper centralizes 204/304 success check for start/stop/restart"
  - "ContainerStats.Id is set from the input id (not from Docker stats response, which lacks it)"
  - "ContainerStats.Name/Image/State left empty string in GetContainerStats — caller uses ListContainers for those fields"
  - "containersStop/Start/Restart return {success, error} dict (not starlark.None) for Starlark-side error handling"

requirements-completed: [AGENT-01, AGENT-02, AGENT-03]

# Metrics
duration: 20min
completed: 2026-05-04
---

# Phase 3 Plan 02: Docker Engine API client and sys.containers Starlark builtins Summary

**Real Docker Engine API over Unix socket: list, stats, stop, start, restart — with mocked tests via baseURL injection and D-02/T-03-06/T-03-07 mitigations**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-04T14:03:00Z
- **Completed:** 2026-05-04T14:22:56Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Expanded docker_client.go with 5 API methods (ListContainers, GetContainerStats, StartContainer, StopContainer, RestartContainer) — all URL construction uses `dc.baseURL` (not hardcoded host)
- `isValidContainerID()` validates ID against `[a-zA-Z0-9_.-]+` before URL construction (T-03-06 path injection mitigation)
- `GetContainerStats` always uses `?stream=false` (T-03-07 DoS mitigation via Pitfall 1 avoidance)
- CPU% calculated as `(cpuDelta/sysDelta) * onlineCPUs * 100` with division-by-zero guards; Mem% = `usage/limit * 100`
- Network bytes summed across all interfaces in the `networks` map
- Created sys_containers.go implementing all 5 Starlark builtins — `containersList` logs error and returns empty list on Docker unavailability (D-02)
- Removed 5 container stub methods from sysscript.go (now in sys_containers.go); k3s stubs kept for Plan 03
- Created sys_containers_test.go with 9 tests covering all methods; all pass with httptest.Server mock

## Task Commits

Each task was committed atomically in the systemapi.io repo:

1. **Task 1: Docker client methods + sys.containers builtins** - `2d5835c` (feat)
2. **Task 2: Docker client and sys.containers unit tests** - `64ff6e7` (test)

## Files Created/Modified

- `systemapi-agent/docker_client.go` — Added DockerStatsResponse, ContainerStats types; ListContainers, GetContainerStats, StartContainer, StopContainer, RestartContainer, isValidContainerID, doContainerPost
- `systemapi-agent/sys_containers.go` — containersList, containersStats, containersStop, containersStart, containersRestart, containerActionResult helper
- `systemapi-agent/sys_containers_test.go` — TestContainersList, TestContainersListEmpty, TestContainersListDockerDown, TestContainersStats, TestContainersStatsStreamFalse, TestContainersStop, TestContainersStart, TestContainersRestart, TestContainerIDValidation
- `systemapi-agent/sysscript.go` — Removed 5 container stub methods; comment updated

## Decisions Made

- `doContainerPost` helper centralizes 204/304 success logic for start/stop/restart endpoints — avoids repeating switch statement in each method
- `ContainerStats.Name/Image/State` are left as empty string in `GetContainerStats` — the Docker `/stats` endpoint does not return container metadata, only resource metrics. Callers that need name/image should use `ListContainers` first
- `containersStop/Start/Restart` return `{success, error}` dict (not error to Starlark) — consistent with sys_config.go pattern; allows scripts to inspect failure without crashing
- k3s stubs (`k3sNodes`, `k3sPods`, `k3sApply`) kept in sysscript.go — Plan 03 will move them to sys_k3s.go

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met. All 9 tests pass.

## Known Stubs

None in the files modified by this plan. The k3s stubs remaining in sysscript.go are intentional carryover from Plan 01, tracked for replacement in Plan 03.

## Self-Check: PASSED

- `systemapi-agent/docker_client.go` exists: FOUND
- `systemapi-agent/sys_containers.go` exists: FOUND
- `systemapi-agent/sys_containers_test.go` exists: FOUND
- Commit `2d5835c` exists: FOUND
- Commit `64ff6e7` exists: FOUND
- `go build ./...` exits 0: VERIFIED
- `go test -run "TestContainers|TestContainerID" -v` exits 0 (9 tests pass): VERIFIED
- `grep "stream=false" docker_client.go` matches: VERIFIED
- `grep "isValidContainerID" docker_client.go` matches: VERIFIED
- `grep -c "func (engine \*SysscriptEngine) containers" sys_containers.go` = 5: VERIFIED
- `grep "dc.baseURL" docker_client.go` matches (5 occurrences): VERIFIED

---
*Phase: 03-systemapi-agent-improvements*
*Completed: 2026-05-04*
