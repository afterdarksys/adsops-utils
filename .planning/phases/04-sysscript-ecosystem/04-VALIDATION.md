---
phase: 4
slug: sysscript-ecosystem
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.3 |
| **Config file** | `tools/adsops/pyproject.toml` |
| **Quick run command** | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/ -x -q` |
| **Full suite command** | `cd tools/adsops && python3.10 -m pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd tools/adsops && python3.10 -m pytest tests/sysscripts/ -x -q`
- **After every plan wave:** Run `cd tools/adsops && python3.10 -m pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | STAR-07 | T-04-01 | load() rejects paths outside sysscripts/ | unit | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/test_runner.py -x -q` | no (W0) | pending |
| 4-01-02 | 01 | 1 | STAR-07 | T-04-04 | CLI error output to stderr, no stack traces | unit | `cd tools/adsops && python3.10 -c "from adsops.sysscript.cli import app; print('ok')"` | no (W0) | pending |
| 4-02-01 | 02 | 2 | STAR-01 | T-04-05 | N/A | unit | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/test_host_star.py -x -q` | no (W0) | pending |
| 4-02-02 | 02 | 2 | STAR-02, STAR-03, STAR-07 | T-04-06 | N/A | unit | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/test_docker_star.py tests/sysscripts/test_k3s_star.py -x -q` | no (W0) | pending |
| 4-03-01 | 03 | 3 | STAR-04, STAR-05 | T-04-07 | config.get for base URL, no hardcoded hosts | unit | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/test_statsagent_health.py tests/sysscripts/test_changes_api_health.py -x -q` | no (W0) | pending |
| 4-03-02 | 03 | 3 | STAR-06 | T-04-09 | Malformed metrics body yields None, not crash | unit | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/test_changes_api_stats.py -x -q` | no (W0) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tools/adsops/tests/sysscripts/__init__.py` — test package init
- [ ] `tools/adsops/tests/sysscripts/test_runner.py` — covers STAR-07 (runner exec, load, sandbox)
- [ ] `tools/adsops/tests/sysscripts/test_host_star.py` — covers STAR-01
- [ ] `tools/adsops/tests/sysscripts/test_docker_star.py` — covers STAR-02
- [ ] `tools/adsops/tests/sysscripts/test_k3s_star.py` — covers STAR-03
- [ ] `tools/adsops/tests/sysscripts/test_statsagent_health.py` — covers STAR-04
- [ ] `tools/adsops/tests/sysscripts/test_changes_api_health.py` — covers STAR-05
- [ ] `tools/adsops/tests/sysscripts/test_changes_api_stats.py` — covers STAR-06

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `changes-api/stats.star` returns real Prometheus data from live host | STAR-06 | Requires live changes-api host with /metrics endpoint | Run `adsops sysscript run sysscripts/services/changes-api/stats.star` with real `changes_api_url` injected |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
