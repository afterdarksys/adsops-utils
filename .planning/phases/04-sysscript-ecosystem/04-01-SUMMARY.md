---
phase: 04-sysscript-ecosystem
plan: "01"
subsystem: sysscript-runner
tags: [python, starlark, exec, cli, tdd]
dependency_graph:
  requires: []
  provides:
    - adsops.sysscript.runner.SysscriptRunner
    - adsops.sysscript.cli.app
    - adsops sysscript run <CLI command>
  affects:
    - tools/adsops/src/adsops/cli.py
tech_stack:
  added: []
  patterns:
    - Python exec()-based Starlark runner (no starlark-py package — doesn't exist on PyPI)
    - Typer sub-app registration via try/except in main cli.py
    - MockSys injected as predefined global before exec()
key_files:
  created:
    - tools/adsops/src/adsops/sysscript/runner.py
    - tools/adsops/src/adsops/sysscript/cli.py
    - tools/adsops/tests/sysscripts/__init__.py
    - tools/adsops/tests/sysscripts/test_runner.py
  modified:
    - tools/adsops/src/adsops/cli.py
decisions:
  - "exec()-based runner confirmed: starlark-py absent from PyPI; exec() is the correct approach"
  - "PYTHONPATH override required for tests in worktree: editable install points to main repo"
metrics:
  duration: "3 minutes"
  completed: "2026-05-04"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 04 Plan 01: SysscriptRunner and CLI Summary

## One-Liner

exec()-based Starlark runner with load() resolution, sysscripts/ sandbox enforcement, and `adsops sysscript run` CLI command backed by empty MockSys.

## What Was Built

### Task 1: SysscriptRunner (TDD)

`tools/adsops/src/adsops/sysscript/runner.py` implements `SysscriptRunner`:

- `_find_sysscripts_root(path)`: walks path ancestors to find a directory named `sysscripts/` (D-07); raises ValueError if not found
- `_resolve_load(load_path, script_dir, root)`: resolves load() path relative to script dir, checks resolved path is within sysscripts root via `startswith(root + os.sep) or == root` (T-04-01, Pitfall 6 guard)
- `run(script_path)`: reads script, pre-execs all load() targets into a shared globals dict (with `sys=MockSys()` pre-injected), strips load() statements, execs main script, returns globals

Six unit tests cover: simple expression eval, sys global injection, load() resolution via helper function, path traversal rejection, missing sysscripts/ ancestor, and NotImplementedError on empty MockSys call.

### Task 2: sysscript CLI Sub-App

`tools/adsops/src/adsops/sysscript/cli.py` provides a Typer sub-app with one command:
- `run <script>`: invokes `SysscriptRunner()` (empty MockSys, D-04); surfaces NotImplementedError as "Script needs fixture: ..." and ValueError as "ERROR: ..." to stderr

`tools/adsops/src/adsops/cli.py` updated with try/except block registering `sysscript_app` under name `"sysscript"`, matching the hostctl/infractl/stats pattern.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

### Notes

**PYTHONPATH worktree override:** The adsops package is installed in editable mode pointing to `/Users/ryan/development/adsops-utils/tools/adsops` (main repo). Tests run in the worktree require `PYTHONPATH` set to the worktree's `src/` directory to pick up the new `runner.py`. Tests were verified with `PYTHONPATH=.../worktrees/agent-ae150aa0/tools/adsops/src`. After wave merge, the editable install will resolve to the correct files automatically.

## TDD Gate Compliance

- RED gate: commit `f391fd0` — `test(04-01): add failing tests for SysscriptRunner`
- GREEN gate: commit `80379b7` — `feat(04-01): implement SysscriptRunner with load() resolution and sandbox`
- REFACTOR: not needed

## Verification

All 6 runner tests pass:
```
cd tools/adsops && PYTHONPATH=src python3.10 -m pytest tests/sysscripts/test_runner.py -x -q
...... 6 passed in 0.04s
```

CLI imports verified:
```
from adsops.sysscript.cli import app  # ok
from adsops.cli import app             # ok
```

## Known Stubs

None.

## Threat Flags

None — all threat model mitigations from the plan were implemented:
- T-04-01/02: Path traversal protection in `_resolve_load` via `pathlib.resolve()` + startswith check
- T-04-04: Errors written to stderr only; no stack traces on stdout

## Self-Check

Files created:
- tools/adsops/src/adsops/sysscript/runner.py — FOUND
- tools/adsops/src/adsops/sysscript/cli.py — FOUND
- tools/adsops/tests/sysscripts/__init__.py — FOUND
- tools/adsops/tests/sysscripts/test_runner.py — FOUND

Commits:
- f391fd0 (RED: failing tests)
- 80379b7 (GREEN: runner implementation)
- 483c2c7 (feat: CLI sub-app)
