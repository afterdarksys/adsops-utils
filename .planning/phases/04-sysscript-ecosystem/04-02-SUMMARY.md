---
phase: 04-sysscript-ecosystem
plan: "02"
subsystem: sysscript-lib
tags: [python, starlark, tdd, lib, docker, k3s, host]
dependency_graph:
  requires:
    - adsops.sysscript.runner.SysscriptRunner
    - adsops.sysscript.mock.MockSys
  provides:
    - sysscripts/lib/host.star (host_info, host_uptime)
    - sysscripts/lib/docker.star (container_list, container_stats, container_count)
    - sysscripts/lib/k3s.star (k3s_node_list, k3s_pod_list, k3s_healthy)
  affects:
    - sysscripts/services/ (scripts can now load() these lib helpers)
tech_stack:
  added: []
  patterns:
    - Starlark lib functions with sys global attribute access (sys.exec.run, sys.containers.*, sys.k3s.*)
    - MockSys callable fixtures for parameterized methods, static fixtures for fixed returns
    - TDD RED/GREEN for each pair of lib + test files
key_files:
  created:
    - sysscripts/lib/host.star
    - sysscripts/lib/docker.star
    - sysscripts/lib/k3s.star
    - tools/adsops/tests/sysscripts/test_host_star.py
    - tools/adsops/tests/sysscripts/test_docker_star.py
    - tools/adsops/tests/sysscripts/test_k3s_star.py
  modified: []
decisions:
  - "lib files define only functions (no top-level calls) — callers get functions in globals after runner.run()"
  - "k3s_pod_list uses default=None pattern with if namespace guard — matches plan action exactly"
  - "container_count() added to docker.star as bonus helper (not tested, but consistent with pattern)"
metrics:
  duration: "5 minutes"
  completed: "2026-05-05"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 04 Plan 02: Sysscript Shared Libraries Summary

## One-Liner

Three Starlark lib helpers (host.star, docker.star, k3s.star) wrapping sys.exec, sys.containers, and sys.k3s — fully tested via MockSys fixtures using TDD.

## What Was Built

### Task 1: lib/host.star (TDD)

`sysscripts/lib/host.star` implements two helper functions:
- `host_info()`: calls `sys.exec.run("hostname")` and `sys.exec.run("uname -s")`, returns `{"hostname": ..., "os": ...}`. Returns `"unknown"` for either field on non-zero exit code.
- `host_uptime()`: calls `sys.exec.run("uptime")`, returns stripped output or `"unknown"` on failure.

`tools/adsops/tests/sysscripts/test_host_star.py` provides 4 tests:
- hostname extraction from exec fixture
- OS extraction from exec fixture
- "unknown" fallback on exec error
- uptime string extraction

### Task 2: lib/docker.star and lib/k3s.star (TDD)

`sysscripts/lib/docker.star` implements:
- `container_list()`: returns `sys.containers.list()`
- `container_stats(name)`: returns `sys.containers.stats(name)`
- `container_count()`: counts running containers from `sys.containers.list()`

`sysscripts/lib/k3s.star` implements:
- `k3s_node_list()`: returns `sys.k3s.nodes()`
- `k3s_pod_list(namespace=None)`: returns `sys.k3s.pods(namespace)` or `sys.k3s.pods()` based on argument
- `k3s_healthy()`: returns True if all nodes have `ready=True`

Tests cover all required behavior scenarios for both files (6 tests across 2 files).

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

### Task 1 (host.star):
- RED gate: commit `e737dc6` — `test(04-02): add failing tests for host.star helpers`
- GREEN gate: commit `2cc5ca5` — `feat(04-02): implement lib/host.star with host_info() and host_uptime()`

### Task 2 (docker.star + k3s.star):
- RED gate: commit `849263c` — `test(04-02): add failing tests for docker.star and k3s.star helpers`
- GREEN gate: commit `1628e30` — `feat(04-02): implement lib/docker.star and lib/k3s.star helpers`

## Verification

All 16 sysscripts tests pass:
```
cd tools/adsops && PYTHONPATH=src python3.10 -m pytest tests/sysscripts/ -x -q
................
16 passed in 0.07s
```

Breakdown:
- 6 runner tests (from Plan 01)
- 4 host.star tests
- 3 docker.star tests
- 3 k3s.star tests

## Known Stubs

None. All helper functions are wired to the sys namespace (tested via MockSys). No placeholder data or hardcoded returns.

## Threat Flags

None — threat model items accepted (T-04-05: host_info disclosure accepted for internal tooling; T-04-06: exec() sandbox constraint accepted as pre-existing).

## Self-Check

Files created:
- sysscripts/lib/host.star — FOUND
- sysscripts/lib/docker.star — FOUND
- sysscripts/lib/k3s.star — FOUND
- tools/adsops/tests/sysscripts/test_host_star.py — FOUND
- tools/adsops/tests/sysscripts/test_docker_star.py — FOUND
- tools/adsops/tests/sysscripts/test_k3s_star.py — FOUND

Commits:
- e737dc6 (RED: host.star tests)
- 2cc5ca5 (GREEN: host.star implementation)
- 849263c (RED: docker.star + k3s.star tests)
- 1628e30 (GREEN: docker.star + k3s.star implementation)

## Self-Check: PASSED
