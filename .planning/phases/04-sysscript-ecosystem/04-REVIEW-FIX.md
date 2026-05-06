---
phase: 04-sysscript-ecosystem
fixed_at: 2026-05-04T00:00:00Z
review_path: .planning/phases/04-sysscript-ecosystem/04-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-05-04
**Source review:** .planning/phases/04-sysscript-ecosystem/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (CR + WR): 9
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: Sandbox bypass — entry-point script not checked to be inside sysscripts root

**Files modified:** `tools/adsops/src/adsops/sysscript/runner.py`
**Commit:** 528f048
**Applied fix:** Added explicit entry-point path check in `run()`: after discovering root via `_find_sysscripts_root`, resolves root and verifies `str(path).startswith(str(root_resolved) + os.sep)` before reading the script. Raises `ValueError` with a descriptive message on violation.

---

### CR-02: Sandbox bypass — `_LOAD_PATTERN` does not match all load() variants

**Files modified:** `tools/adsops/src/adsops/sysscript/runner.py`
**Commit:** 528f048
**Applied fix:** After stripping load() from the main script, asserts no residual `load\s*\(` tokens remain via `re.search(r'\bload\s*\(', main_src)`. Any unrecognised load() syntax raises `ValueError` rather than silently passing. Lib file handling is addressed under WR-03 (same commit).

---

### CR-03: `None` config value causes unguarded `TypeError` in service scripts

**Files modified:** `sysscripts/services/statsagent/health.star`, `sysscripts/services/changes-api/health.star`, `sysscripts/services/changes-api/stats.star`
**Commit:** e9ef955
**Applied fix:** All three service scripts now guard `sys.config.get()` results with `if not base_url:` before concatenation. On missing config, scripts print a descriptive `ERROR:` message and set a safe default (`healthy = False`) or skip execution of the dependent block. stats.star wraps the entire metrics fetch and parse in the else branch.

---

### CR-04: `exec()` globals gives scripts access to full Python builtins

**Files modified:** `tools/adsops/src/adsops/sysscript/runner.py`
**Commit:** 528f048
**Applied fix:** Added module-level `_SAFE_BUILTINS` dict with an explicit allowlist of safe builtins (`len`, `range`, `print`, `str`, `int`, `float`, `bool`, `list`, `dict`, `all`, `any`, `None`, `True`, `False`). Changed `globs` to `{"sys": self._sys, "__builtins__": _SAFE_BUILTINS}`, preventing access to `__import__`, `open`, `eval`, and the rest of the builtins module. Applied to both the lib exec and main script exec paths.

---

### WR-01: `cli.py` does not catch `FileNotFoundError` or `PermissionError`

**Files modified:** `tools/adsops/src/adsops/sysscript/cli.py`
**Commit:** 5b9781b
**Applied fix:** Added `except (FileNotFoundError, PermissionError) as e:` handler in `run_cmd()` that prints a clean error message and exits with code 1 instead of surfacing a raw traceback.

---

### WR-02: `cli.py` does not catch `SyntaxError` from `compile()`

**Files modified:** `tools/adsops/src/adsops/sysscript/cli.py`
**Commit:** 5b9781b
**Applied fix:** Added `except SyntaxError as e:` handler in `run_cmd()` that prints `ERROR: Script syntax error: {e}` (which includes file and line number from the exception) and exits with code 1.

---

### WR-03: Recursive `load()` in lib files is silently dropped, not rejected

**Files modified:** `tools/adsops/src/adsops/sysscript/runner.py`
**Commit:** 528f048
**Applied fix:** Replaced the silent `_LOAD_PATTERN.sub("", lib_src)` strip with a check: `if _LOAD_PATTERN.search(lib_src): raise ValueError(...)`. Lib files containing any load() now immediately raise `ValueError` with the lib file path named, rather than silently dropping the dependency and producing mysterious `NameError` at runtime.

---

### WR-04: `request_count` may be `None` and is printed without guard

**Files modified:** `sysscripts/services/changes-api/stats.star`
**Commit:** e9ef955
**Applied fix:** Changed the `print("request_count:", request_count)` line to use a conditional expression: `request_count if request_count is not None else "N/A (metric not found)"`. This clearly distinguishes a missing metric from a metric with a null value.

---

### WR-05: `_find_sysscripts_root` matches any ancestor — ambiguous sandbox root

**Files modified:** `tools/adsops/src/adsops/sysscript/runner.py`
**Commit:** 0d0b98f
**Applied fix:** Added `sysscripts_root: Optional[str] = None` parameter to `SysscriptRunner.__init__()`. When provided, it is resolved once and stored as `self._root_override`. In `run()`, the override is used directly when set, falling back to `_find_sysscripts_root()` auto-discovery only when not provided. Added `from typing import Optional` import. This lets callers (CLI, tests) pin the sandbox root to a known-safe path.

---

_Fixed: 2026-05-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
