---
phase: 3
slug: systemapi-agent-improvements
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | go test |
| **Config file** | none — standard Go toolchain |
| **Quick run command** | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test ./... -short` |
| **Full suite command** | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test ./...` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `go test ./... -short`
- **After every plan wave:** Run `go test ./...`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | AGENT-06 | — | DockerClient struct with baseURL field compiles | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go build ./...` | N/A (build check) | ⬜ pending |
| 3-01-02 | 01 | 1 | AGENT-06 | T-03-04 | Entitlement enforcement: containers/k3s absent when not entitled | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestEntitlement" -v -short` | ❌ W0 (sysscript_test.go) | ⬜ pending |
| 3-01-03 | 01 | 1 | AGENT-06 | T-03-01 | Thread.Load path traversal rejected; file-not-found fails fast | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestThreadLoad" -v -short` | ❌ W0 (sysscript_test.go) | ⬜ pending |
| 3-02-01 | 02 | 2 | AGENT-01 | T-03-06 | sys.containers.list() returns containers from mocked Docker API | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestContainersList" -v` | ❌ W0 (sys_containers_test.go) | ⬜ pending |
| 3-02-02 | 02 | 2 | AGENT-02, AGENT-03 | T-03-07 | stats/stop/start/restart with mocked API and ID validation | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestContainers|TestContainerID" -v` | ❌ W0 (sys_containers_test.go) | ⬜ pending |
| 3-03-01 | 03 | 2 | AGENT-04 | — | sys.k3s.nodes() and pods() from mocked k8s API | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestK3s" -v` | ❌ W0 (sys_k3s_test.go) | ⬜ pending |
| 3-03-02 | 03 | 2 | AGENT-04 | T-03-09 | Namespace validation rejects path traversal values | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestNamespaceValidation" -v` | ❌ W0 (sys_k3s_test.go) | ⬜ pending |
| 3-04-01 | 04 | 3 | AGENT-05 | — | TelemetryPayload includes Docker and K3s fields; gather functions work | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestTelemetry" -v` | ❌ W0 (telemetry_test.go) | ⬜ pending |
| 3-04-02 | 04 | 3 | AGENT-06 | — | JSON tags match proto-compatible values; rx_bytes/tx_bytes (not per_sec) | unit | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test -run "TestTelemetryStructTags" -v` | ❌ W0 (telemetry_test.go) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `sysscript_test.go` — stubs for entitlement enforcement (TestEntitlement*) and Thread.Load (TestThreadLoad*)
- [ ] `sys_containers_test.go` — stubs for Docker container operations (TestContainers*, TestContainerID*)
- [ ] `sys_k3s_test.go` — stubs for k3s operations (TestK3s*, TestResourcePath, TestNamespaceValidation)
- [ ] `telemetry_test.go` — stubs for telemetry extension (TestTelemetry*, TestTelemetryStructTags)

*All test files must compile with `go test ./... -short` before implementation begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker socket reads live container data on host | AGENT-01 | Requires Docker daemon running | Run `sudo ./systemapi-agent` and verify telemetry payload includes container list |
| k3s nodes() returns real cluster nodes | AGENT-04 | Requires k3s installed on host | Run agent on k3s node; inspect telemetry for `k3s` field |
| load("lib/helper.star", "fn") executes without error | AGENT-05 | Requires script file on disk | Place helper.star at `/etc/systemapi/scripts/lib/helper.star`; run test sysscript |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
