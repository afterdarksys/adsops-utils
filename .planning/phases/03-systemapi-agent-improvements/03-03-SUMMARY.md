---
phase: 03-systemapi-agent-improvements
plan: 03
subsystem: infra
tags: [go, starlark, k3s, kubernetes, sysscript, testing, security]

# Dependency graph
requires:
  - phase: 03-systemapi-agent-improvements
    plan: 01
    provides: "K3sClient stub with TLS from kubeconfig, k3s method stubs in sysscript.go, Entitlements.AllowK3s"
provides:
  - "K3sClient with ListNodes, ListPods, Apply methods (raw HTTP, no client-go)"
  - "isValidNamespace() for T-03-09 namespace path-injection prevention"
  - "resourcePath() for kind/apiVersion to k8s API path mapping"
  - "Apply() with POST-create and 409-conflict PATCH retry"
  - "sys_k3s.go: k3sNodes, k3sPods, k3sApply Starlark builtins"
  - "D-05: k3sNodes/k3sPods return empty list on k3s unavailability"
  - "sys_k3s_test.go: 10 tests with httptest.Server mock via serverURL injection"
affects: [03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httptest.Server injected via K3sClient.serverURL for unit testing k8s API calls"
    - "D-05: log + return empty list on k3s unavailability (never propagate to Starlark)"
    - "isValidNamespace: [a-z0-9-]+ charset, len 1-253 — rejects /, .., uppercase, spaces"
    - "Apply: POST to create, PATCH with strategic-merge on 409 Conflict"
    - "YAML->JSON via yaml.v3 unmarshal + json.Marshal with normalizeYAMLForJSON helper"
    - "starlarkstruct.FromStringDict for typed node/pod return values"
    - "Optional namespace arg via UnpackArgs 'namespace?' suffix (same pattern as sys_net_proc.go dns_lookup)"

key-files:
  created:
    - systemapi-agent/sys_k3s.go
    - systemapi-agent/sys_k3s_test.go
  modified:
    - systemapi-agent/k3s_client.go
    - systemapi-agent/sysscript.go

key-decisions:
  - "YAML-to-JSON conversion uses yaml.v3 unmarshal + json.Marshal with normalizeYAMLForJSON to handle map[interface{}]interface{} from older yaml.v3 versions"
  - "isValidNamespace rejects dots (.) to strictly follow k8s namespace naming [a-z0-9-]+ — no uppercase, no dots, no slashes"
  - "doPatch is a private helper on K3sClient that sets Content-Type: application/strategic-merge-patch+json"
  - "k3sApply returns {success, error} dict even on client-not-initialized — consistent with sys_config.go pattern"

requirements-completed: [AGENT-04]

# Metrics
duration: 15min
completed: 2026-05-04
---

# Phase 3 Plan 03: Kubernetes REST API client and sys.k3s Starlark builtins Summary

**Raw HTTP Kubernetes API client (no client-go): ListNodes, ListPods, Apply with namespace validation and conflict retry — 10 passing tests via httptest mock injection**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-04T14:12:00Z
- **Completed:** 2026-05-04T14:27:38Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Expanded k3s_client.go with K8sNodeList/K8sNode/K8sPodList/K8sPod response types; added ListNodes(), ListPods(namespace), Apply(yamlStr), resourcePath(), isValidNamespace(), doPatch(), normalizeYAMLForJSON()
- `isValidNamespace()` validates namespace against `[a-z0-9-]+` before URL construction (T-03-09 path injection mitigation)
- `Apply()` POSTs to create, retries with strategic-merge PATCH on 409 Conflict; YAML converted to JSON via yaml.v3+json.Marshal
- Created sys_k3s.go implementing k3sNodes, k3sPods, k3sApply Starlark builtins — k3sNodes/k3sPods log error and return empty list on k3s unavailability (D-05)
- Removed 3 k3s stub methods from sysscript.go (now in sys_k3s.go); containers stubs were already removed by Plan 02
- Created sys_k3s_test.go with 10 tests covering all methods; all pass with httptest.Server mock

## Task Commits

Each task was committed atomically in the systemapi.io repo:

1. **Task 1: k3s client methods + sys.k3s builtins** - `db922e3` (feat)
2. **Task 2: k3s client and sys.k3s unit tests** - `81312e1` (test)

## Files Created/Modified

- `systemapi-agent/k3s_client.go` — Added K8sNodeList, K8sNode, K8sPodList, K8sPod types; isValidNamespace, resourcePath, ListNodes, ListPods, Apply, doPatch, normalizeYAMLForJSON
- `systemapi-agent/sys_k3s.go` — k3sNodes, k3sPods, k3sApply Starlark builtins
- `systemapi-agent/sys_k3s_test.go` — TestK3sNodes, TestK3sNodesEmpty, TestK3sNodesUnavailable, TestK3sPods, TestK3sPodsOptionalNamespace, TestK3sApplyCreate, TestK3sApplyConflict, TestK3sApplyInvalidYAML, TestResourcePath, TestNamespaceValidation
- `systemapi-agent/sysscript.go` — Removed 3 k3s placeholder stubs (k3sNodes, k3sPods, k3sApply)

## Decisions Made

- `normalizeYAMLForJSON` helper normalizes `map[interface{}]interface{}` produced by yaml.v3 on some Go versions — ensures `json.Marshal` always gets `map[string]interface{}`
- `isValidNamespace` rejects dots — strictly follows Kubernetes namespace naming rules (`[a-z0-9-]+`); dots are valid in DNS names but not namespace names per k8s spec
- `doPatch` is a private K3sClient method for `application/strategic-merge-patch+json` — avoids duplicating PATCH logic in Apply
- `k3sApply` Starlark builtin returns `{success, error}` dict consistent with `sys_config.go` pattern; callers can inspect failure without Starlark error propagation

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met. All 10 tests pass.

## Known Stubs

None. All k3s stubs from Plan 01 have been replaced with full implementations.

## Threat Mitigations Implemented

| Threat ID | Mitigation | Verification |
|-----------|-----------|-------------|
| T-03-09 | `isValidNamespace()` validates `[a-z0-9-]+` before URL construction | TestNamespaceValidation (10 cases) |
| T-03-03 | No kubeconfig credential data logged — only file paths and connection errors | Code review: log lines in sys_k3s.go log only error messages |
| D-05 | k3sNodes/k3sPods return empty list on any k3s error | TestK3sNodesUnavailable |

## Self-Check: PASSED

- `systemapi-agent/k3s_client.go` exists: FOUND
- `systemapi-agent/sys_k3s.go` exists: FOUND
- `systemapi-agent/sys_k3s_test.go` exists: FOUND
- Commit `db922e3` exists: FOUND
- Commit `81312e1` exists: FOUND
- `go build ./...` exits 0: VERIFIED
- `go test -run "TestK3s|TestResourcePath|TestNamespace" -v` exits 0 (10 tests pass): VERIFIED
- `grep -c "func (engine *SysscriptEngine) k3s" sys_k3s.go` = 3: VERIFIED
- `grep -c "func (kc *K3sClient)" k3s_client.go` >= 3 (= 4): VERIFIED
- `grep "isValidNamespace" k3s_client.go` matches: VERIFIED
- `grep "func (engine *SysscriptEngine) k3sNodes" sysscript.go` = 0 (stubs removed): VERIFIED

---
*Phase: 03-systemapi-agent-improvements*
*Completed: 2026-05-04*
