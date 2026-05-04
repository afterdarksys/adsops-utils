---
phase: 2
slug: python3-package
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tools/adsops/pyproject.toml or pytest.ini — Wave 0 installs |
| **Quick run command** | `python3.11 -m pytest tools/adsops/ -x -q` |
| **Full suite command** | `python3.11 -m pytest tools/adsops/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3.11 -m pytest tools/adsops/ -x -q`
- **After every plan wave:** Run `python3.11 -m pytest tools/adsops/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | PY-01 | — | N/A | unit | `pip install -e tools/adsops/ && adsops --help` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | PY-02 | — | N/A | unit | `python3.11 -m pytest tools/adsops/tests/test_hostctl.py -v` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | PY-03 | — | N/A | unit | `python3.11 -m pytest tools/adsops/tests/test_infractl.py -v` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | PY-04 | — | N/A | unit | `python3.11 -m pytest tools/adsops/tests/test_stats.py -v` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | PY-05 | — | N/A | unit | `python3.11 -m pytest tools/adsops/tests/test_mocksys.py -v` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | PY-06 | — | N/A | unit | `python3.11 -m pytest tools/adsops/tests/ -v` | ❌ W0 | ⬜ pending |
| 02-03-03 | 03 | 3 | PY-07 | — | N/A | integration | `python3.11 -m pytest tools/adsops/tests/ -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tools/adsops/tests/__init__.py` — test package init
- [ ] `tools/adsops/tests/conftest.py` — shared fixtures (MockSys, tmp DB)
- [ ] `tools/adsops/tests/test_hostctl.py` — stubs for PY-02
- [ ] `tools/adsops/tests/test_infractl.py` — stubs for PY-03
- [ ] `tools/adsops/tests/test_stats.py` — stubs for PY-04
- [ ] `tools/adsops/tests/test_mocksys.py` — stubs for PY-05, PY-06
- [ ] `asyncssh` installed in python3.11 environment

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSH agent forwarding works with live host | PY-03 | Requires real SSH agent and remote Docker host | `adsops infractl docker ls <real-host>` with `SSH_AUTH_SOCK` set |
| Stats output formatting | PY-04 | Requires human review of output readability | `adsops stats once` and verify output is human-readable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
