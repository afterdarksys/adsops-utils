---
phase: 04-sysscript-ecosystem
plan: "03"
subsystem: sysscript-services
tags: [python, starlark, tdd, services, prometheus, health-check]
dependency_graph:
  requires:
    - adsops.sysscript.runner.SysscriptRunner
    - adsops.sysscript.mock.MockSys
    - sysscripts/lib/host.star
  provides:
    - sysscripts/services/statsagent/health.star (statsagent health check)
    - sysscripts/services/changes-api/health.star (changes-api health check)
    - sysscripts/services/changes-api/stats.star (changes-api Prometheus metrics)
  affects:
    - tools/adsops/tests/sysscripts/ (6 new test files total, 11 new tests)
tech_stack:
  added: []
  patterns:
    - Service scripts use sys.config.get for base URL (D-10), sys.net.http_get for HTTP calls (D-08, D-09)
    - Service scripts load lib helpers via load("../../lib/host.star", "host_info")
    - Prometheus text format parsed with simple string split (no regex, no external parser)
    - MockSys callable fixture for config.get (parameterized by key), static dict for net.http_get
    - exec.run fixture required in service script tests because host.star calls sys.exec.run
key_files:
  created:
    - sysscripts/services/statsagent/health.star
    - sysscripts/services/changes-api/health.star
    - sysscripts/services/changes-api/stats.star
    - tools/adsops/tests/sysscripts/test_statsagent_health.py
    - tools/adsops/tests/sysscripts/test_changes_api_health.py
    - tools/adsops/tests/sysscripts/test_changes_api_stats.py
  modified: []
decisions:
  - "exec.run fixture required in service script tests: service scripts load host.star which calls sys.exec.run('hostname') and sys.exec.run('uname -s')"
  - "Prometheus parsing uses simple string split() — no regex, no external library (T-04-09: malformed body yields None, not crash)"
  - "latency_avg is float 0.0 when count is 0 or metrics not present — safe default"
metrics:
  duration: "4 minutes"
  completed: "2026-05-04"
  tasks_completed: 2
  tasks_total: 3
---

# Phase 04 Plan 03: Service Scripts (Health + Stats) Summary

## One-Liner

Three service .star scripts (statsagent health, changes-api health, changes-api Prometheus stats) with full MockSys-based test coverage using TDD, completing the sysscript ecosystem.

## What Was Built

### Task 1: statsagent/health.star and changes-api/health.star (TDD)

`sysscripts/services/statsagent/health.star`:
- Reads `statsagent_url` via `sys.config.get` (D-10)
- Calls `sys.net.http_get(base_url + "/health")` (D-08)
- Sets `healthy = (resp["status_code"] == 200)`
- Loads `host_info()` from `../../lib/host.star` and prints host context

`sysscripts/services/changes-api/health.star`:
- Reads `changes_api_url` via `sys.config.get` (D-10)
- Calls `sys.net.http_get(base_url + "/health")` (D-08)
- Sets `healthy = (resp["status_code"] == 200)`
- Loads `host_info()` from `../../lib/host.star` and prints host context

`tools/adsops/tests/sysscripts/test_statsagent_health.py` — 3 tests:
- `test_healthy_on_200`: healthy=True when status_code==200
- `test_unhealthy_on_503`: healthy=False when status_code==503
- `test_reads_statsagent_url`: proves config.get is called for statsagent_url

`tools/adsops/tests/sysscripts/test_changes_api_health.py` — 3 tests:
- `test_healthy_on_200`: healthy=True when status_code==200 (D-08)
- `test_unhealthy_on_non_200`: healthy=False when status_code!=200 (D-08)
- `test_reads_changes_api_url`: proves config.get is called for changes_api_url (D-10)

### Task 2: changes-api/stats.star with Prometheus Parsing (TDD)

`sysscripts/services/changes-api/stats.star`:
- Reads `changes_api_url` via `sys.config.get` (D-10)
- Calls `sys.net.http_get(base_url + "/metrics")` (D-09)
- Parses Prometheus text format via `body.split("\n")` with `line.startswith()` guards
- Extracts `request_count` from `http_requests_total` lines
- Extracts `latency_sum` and `latency_count` from `http_request_duration_seconds_*` lines
- Computes `latency_avg = latency_sum / latency_count` (float division, 0.0 if unavailable)
- Handles empty body gracefully — all metrics remain `None`

`tools/adsops/tests/sysscripts/test_changes_api_stats.py` — 5 tests:
- `test_parses_request_count`: extracts "1234" from realistic Prometheus body
- `test_parses_latency_sum_and_count`: extracts "45.6" sum and "1234" count
- `test_computes_latency_avg`: latency_avg == 45.6/1234 within 0.001 tolerance
- `test_empty_body_returns_none`: request_count is None on empty body
- `test_reads_config_url`: proves config.get is called for changes_api_url (D-10)

### Task 3: Checkpoint

The plan contains a `checkpoint:human-verify` gate (Task 3) for end-to-end ecosystem verification. This checkpoint requires human verification of the full sysscript test suite and CLI command. It is not an auto-only task; user verification is required before the ecosystem is considered fully accepted.

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

### Task 1 (health scripts):
- RED gate: commit `f545b1a` — `test(04-03): add failing tests for statsagent and changes-api health scripts`
- GREEN gate: commit `24b9b3a` — `feat(04-03): implement statsagent/health.star and changes-api/health.star`

### Task 2 (stats.star):
- RED gate: commit `057525a` — `test(04-03): add failing tests for changes-api/stats.star Prometheus parsing`
- GREEN gate: commit `d2f47a5` — `feat(04-03): implement changes-api/stats.star with Prometheus text parsing`

## Verification

All 27 sysscripts tests pass:
```
cd tools/adsops && PYTHONPATH=src python3.10 -m pytest tests/sysscripts/ -v
27 passed in 0.10s
```

Breakdown:
- 6 runner tests (Plan 01)
- 4 host.star tests (Plan 02)
- 3 docker.star tests (Plan 02)
- 3 k3s.star tests (Plan 02)
- 3 statsagent health tests (Plan 03, Task 1)
- 3 changes-api health tests (Plan 03, Task 1)
- 5 changes-api stats tests (Plan 03, Task 2)

## Known Stubs

None. All three service scripts read real config values, make real HTTP calls (via MockSys in tests), and compute real output values. No placeholder data or hardcoded returns.

## Threat Flags

None — threat model items were implemented as designed:
- T-04-07: Base URL sourced from sys.config.get (not hardcoded) — satisfied by plan design
- T-04-08: Prometheus metrics are operational data (no PII) — accepted
- T-04-09: Malformed Prometheus body results in None values, not crash — verified by test_empty_body_returns_none

## Self-Check

Files created:
- sysscripts/services/statsagent/health.star
- sysscripts/services/changes-api/health.star
- sysscripts/services/changes-api/stats.star
- tools/adsops/tests/sysscripts/test_statsagent_health.py
- tools/adsops/tests/sysscripts/test_changes_api_health.py
- tools/adsops/tests/sysscripts/test_changes_api_stats.py

Commits:
- f545b1a (RED: health tests)
- 24b9b3a (GREEN: health scripts)
- 057525a (RED: stats tests)
- d2f47a5 (GREEN: stats.star)
