---
phase: 03-systemapi-agent-improvements
plan: 04
subsystem: infra
tags: [go, telemetry, docker, k3s, websocket, proto-alignment, testing]

# Dependency graph
requires:
  - phase: 03-systemapi-agent-improvements
    plan: 02
    provides: "DockerClient with ListContainers, GetContainerStats"
  - phase: 03-systemapi-agent-improvements
    plan: 03
    provides: "K3sClient with ListNodes, ListPods"
provides:
  - "ContainerStatsTelemetry struct with proto-compatible JSON tags (AGENT-06)"
  - "DockerStatsTelemetry struct with available/total_containers/running_containers/containers fields"
  - "NodeInfoTelemetry struct with name/role/status/version fields"
  - "K3sStatsTelemetry struct with available/total_nodes/ready_nodes/total_pods/running_pods/failed_pods/nodes fields"
  - "TelemetryPayload.Docker and TelemetryPayload.K3s pointer fields (omitempty)"
  - "gatherDockerStats() non-fatal Docker stats collection (D-02: returns available=false on error)"
  - "gatherK3sStats() non-fatal k3s stats collection (D-05: returns nil when k3s unavailable)"
  - "ensureTelemetryClients() with sync.Once for lazy client initialization"
  - "telemetry_test.go: 3 tests for struct tag verification and JSON serialization"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sync.Once for lazy client init: ensureTelemetryClients() called on first gatherTelemetry tick"
    - "Non-fatal Docker/k3s gathering: log error and return available=false/nil, never propagate to WebSocket"
    - "Pointer fields with omitempty: Docker and K3s absent from JSON when service unavailable"
    - "rx_bytes/tx_bytes cumulative counts: diverge from proto per-sec naming for semantic clarity"
    - "reflect-based struct tag testing: TestTelemetryStructTags verifies JSON tag alignment at compile time"

key-files:
  created:
    - systemapi-agent/telemetry_test.go
  modified:
    - systemapi-agent/telemetry.go

key-decisions:
  - "rx_bytes/tx_bytes JSON tags (not rx_bytes_per_sec/tx_bytes_per_sec): Docker stats API returns cumulative bytes; computing rates requires two samples with a time delta, which this single-tick gather does not do. Field names reflect actual semantics."
  - "sync.Once for client init: clients created once on first tick, not at agent startup — avoids Docker/k3s connection errors blocking startup"
  - "Short ID fallback with bounds check: id[:12] guarded by len(c.Id) < 12 check to prevent panic on unexpectedly short container IDs"

requirements-completed: [AGENT-05, AGENT-06]

# Metrics
duration: 12min
completed: 2026-05-04
---

# Phase 3 Plan 04: Telemetry Docker and k3s Extension Summary

**Extended TelemetryPayload with Docker container stats and k3s cluster state — proto-compatible JSON tags, non-fatal gathering, sync.Once lazy init, 3 passing tests**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-04T14:45:00Z
- **Completed:** 2026-05-04T14:57:00Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- Extended telemetry.go with 4 new struct types (ContainerStatsTelemetry, DockerStatsTelemetry, NodeInfoTelemetry, K3sStatsTelemetry) whose JSON tags match the proto definitions for wire compatibility (AGENT-06)
- Added Docker and K3s pointer fields to TelemetryPayload with `json:",omitempty"` so unavailable services produce no JSON keys
- Added gatherDockerStats() and gatherK3sStats() called at ticks 7 and 8 in gatherTelemetry() — both are non-fatal: Docker unavailability returns `available: false` (D-02), k3s unavailability returns nil (D-05)
- Added ensureTelemetryClients() with sync.Once so DockerClient and K3sClient are created exactly once on first tick
- T-03-03 compliance: gatherK3sStats logs only "k3s stats unavailable: <error>" message, never credential data
- Created telemetry_test.go with 3 tests: TestTelemetryStructTags (reflect-based), TestTelemetryPayloadJSON (serialization), TestTelemetryPayloadOmitEmpty (omitempty behavior)
- Confirmed gatherTelemetry() is called from the 5-second ticker in main.go (lines 89-105)
- Full test suite: 22 tests pass, 1 skipped (TestThreadLoadSuccess expected on machines without /etc/systemapi/scripts/)

## Task Commits

Each task was committed atomically in the systemapi.io repo:

1. **Task 1: Telemetry struct extension and gather functions** - `ca8854e` (feat)
2. **Task 2: Telemetry tests including struct tag verification** - `e377d5b` (test)

## Files Created/Modified

- `systemapi-agent/telemetry.go` — Added ContainerStatsTelemetry, DockerStatsTelemetry, NodeInfoTelemetry, K3sStatsTelemetry structs; Docker/K3s fields on TelemetryPayload; ensureTelemetryClients(), gatherDockerStats(), gatherK3sStats(); wired into gatherTelemetry()
- `systemapi-agent/telemetry_test.go` — TestTelemetryStructTags (reflect, verifies all JSON tags), TestTelemetryPayloadJSON (full serialization with docker/k3s), TestTelemetryPayloadOmitEmpty (nil fields absent from JSON)

## Decisions Made

- `rx_bytes`/`tx_bytes` JSON tags instead of `rx_bytes_per_sec`/`tx_bytes_per_sec`: Docker's stats API returns cumulative byte counters, not rates. Computing rates requires two samples — which a single-tick gather does not perform. Using semantically accurate field names avoids confusion at the consumer.
- `sync.Once` for client init: Docker/k3s clients are created lazily on first telemetry tick, not at agent startup. This avoids blocking agent boot on Docker socket/kubeconfig availability.
- Short ID bounds check: `c.Id[:12]` guarded with `if len(c.Id) < 12 { name = c.Id }` to prevent panic on unexpectedly short Docker container IDs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Short ID bounds check added to gatherDockerStats**
- **Found during:** Task 1 implementation review
- **Issue:** Plan code `name := c.Id[:12]` would panic if a Docker container ID is shorter than 12 characters (unlikely in practice but defensive programming)
- **Fix:** Added `if len(c.Id) < 12 { name = c.Id }` before the slice expression
- **Files modified:** systemapi-agent/telemetry.go
- **Commit:** ca8854e

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: bounds check for short container ID)
**Impact on plan:** Minimal — purely defensive. No behavioral change in normal operation.

## Threat Mitigations Verified

| Threat ID | Mitigation | Verification |
|-----------|-----------|-------------|
| T-03-10 | WebSocket auth via api_key already in place (existing design) | No change needed — accept disposition |
| T-03-03 | gatherK3sStats logs only "k3s stats unavailable: <err>", never cert/key data | Code review: log.Printf lines log only error values |

## Known Stubs

None. All Docker and k3s telemetry fields are wired to real client calls. The `available: false` / nil returns on service unavailability are intentional graceful degradation, not stubs.

## Self-Check: PASSED

- `systemapi-agent/telemetry.go` modified: FOUND
- `systemapi-agent/telemetry_test.go` created: FOUND
- Commit `ca8854e` exists: FOUND
- Commit `e377d5b` exists: FOUND
- `go build ./...` exits 0: VERIFIED
- `go test -run "TestTelemetry" -v` exits 0 (3 tests pass): VERIFIED
- `go test ./... -v` exits 0 (22 pass, 1 skip): VERIFIED
- `grep 'json:"docker,omitempty"' telemetry.go` matches: VERIFIED
- `grep 'json:"k3s,omitempty"' telemetry.go` matches: VERIFIED
- `grep 'json:"rx_bytes"' telemetry.go` matches (cumulative, not per_sec): VERIFIED
- `grep "gatherTelemetry" main.go` matches (ticker integration confirmed): VERIFIED
- No `RxBytesPerSec` or `TxBytesPerSec` in telemetry.go: VERIFIED

---
*Phase: 03-systemapi-agent-improvements*
*Completed: 2026-05-04*
