---
phase: 04-sysscript-ecosystem
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - tools/adsops/src/adsops/sysscript/runner.py
  - tools/adsops/src/adsops/sysscript/cli.py
  - tools/adsops/src/adsops/sysscript/mock.py
  - tools/adsops/src/adsops/cli.py
  - sysscripts/lib/host.star
  - sysscripts/lib/docker.star
  - sysscripts/lib/k3s.star
  - sysscripts/services/statsagent/health.star
  - sysscripts/services/changes-api/health.star
  - sysscripts/services/changes-api/stats.star
findings:
  critical: 4
  warning: 5
  info: 2
  total: 11
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This phase implements a `exec()`-based Starlark-subset runner, a Typer CLI sub-app, a MockSys fixture system, and a set of `.star` service/lib scripts. The sandbox enforcement in `runner.py` is the highest-risk surface, and it has two distinct bypasses. The `_LOAD_PATTERN` regex is also incomplete, allowing load() calls to be silently skipped rather than rejected. Additionally, several scripts fail to guard against `None` config values before string concatenation, which will produce unhelpful `TypeError` crashes at runtime. The MockSys comment claims 14 namespaces but 15 are instantiated — a minor audit drift. Overall the architecture is sound but several correctness and security gaps need to be addressed before this ships.

---

## Critical Issues

### CR-01: Sandbox bypass — script file itself is not checked to be inside sysscripts root

**File:** `tools/adsops/src/adsops/sysscript/runner.py:52-59`

**Issue:** `run()` accepts any arbitrary `script_path`, resolves it, then derives `sysscripts_root` by walking ancestors for a directory named `sysscripts`. The sandbox check in `_resolve_load()` guards `load()` targets but there is no equivalent check that the *entry-point script itself* resides within the discovered `sysscripts_root`. An attacker or misconfigured caller can pass any `.py`/`.star` file anywhere on the filesystem (e.g., `/tmp/evil.star`) and it will be executed with full Python globals — the runner will simply fail to find a `sysscripts` ancestor and raise `ValueError`, which the CLI surfaces as an error message, not a sandbox violation. More critically: if the attacker can place a directory named `sysscripts` above their evil script (trivially true on most systems: any path rooted under a user home dir that contains a `sysscripts` dir anywhere above it), the entry-point executes freely.

**Fix:**
```python
def run(self, script_path: str) -> dict:
    path = pathlib.Path(script_path).resolve()
    root = self._find_sysscripts_root(path)
    # Enforce that the entry-point itself is inside the sandbox
    root_resolved = root.resolve()
    if not str(path).startswith(str(root_resolved) + os.sep):
        raise ValueError(
            f"Script {path} is not inside sysscripts root {root_resolved}"
        )
    content = path.read_text()
    ...
```

---

### CR-02: Sandbox bypass — `_LOAD_PATTERN` does not match load() with no symbol arguments

**File:** `tools/adsops/src/adsops/sysscript/runner.py:6-8`

**Issue:** The regex requires at least zero *additional* comma-separated string arguments after the path, but in practice the pattern is:

```
load\(\s*["']([^"']+)["'](?:\s*,\s*["']\w+["'])*\s*\)\n?
```

This matches `load("path")` with no symbols, but Starlark `load()` without any symbols (`load("../../lib/escape.star")`) is valid syntax. More importantly the character class `\w+` for symbol names matches only `[a-zA-Z0-9_]`. A load symbol with a hyphen — which is not valid Starlark but could appear in a hand-crafted attack payload — will cause the regex to **not match**, silently falling through. The consequence is that the unmatched `load()` line is left in the source passed to `exec()`, and Python's `exec()` will raise a `SyntaxError` rather than a sandbox violation. However the more dangerous direction is the inverse: if a load() with a creative path is not matched by the regex, the `_resolve_load` path-traversal check is never invoked for it, and the stripped source still won't execute it under `exec()` (Python doesn't know `load`), so it fails silently rather than traversing. This is a defense-in-depth gap: the sandbox's load-path filtering depends entirely on the regex matching every load() call, and there is no fallback assertion that all load-like strings have been accounted for.

**Fix:** After stripping, assert no residual `load(` tokens remain in the source. This turns a silent miss into a loud rejection:

```python
main_src = _LOAD_PATTERN.sub("", content)
if re.search(r'\bload\s*\(', main_src):
    raise ValueError("Unrecognised load() syntax — cannot safely sandbox this script")
exec(compile(main_src, str(path), "exec"), globs)
```

Apply the same guard after stripping lib sources (line 69).

---

### CR-03: `None` config value causes unguarded `TypeError` (string + None concatenation) in all three service scripts

**File:** `sysscripts/services/statsagent/health.star:3-4`, `sysscripts/services/changes-api/health.star:3-4`, `sysscripts/services/changes-api/stats.star:3-4`

**Issue:** All three scripts follow the pattern:

```python
base_url = sys.config.get("statsagent_url")
resp = sys.net.http_get(base_url + "/health")
```

`sys.config.get()` returns `None` when the key is absent (standard dict/config semantics). In Python `None + "/health"` raises `TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'`. The error message will be opaque to operators ("TypeError" with no mention of which config key is missing). This is a correctness failure that will manifest in production whenever a config key is misconfigured or missing.

**Fix:** Guard each config fetch:

```python
base_url = sys.config.get("statsagent_url")
if not base_url:
    print("ERROR: statsagent_url not configured")
    # exit or return — in Starlark-subset scripts, assign a sentinel and skip
    healthy = False
else:
    resp = sys.net.http_get(base_url + "/health")
    healthy = (resp["status_code"] == 200)
```

---

### CR-04: `exec()` globals dict gives executed scripts access to Python builtins including `__import__`

**File:** `tools/adsops/src/adsops/sysscript/runner.py:62-74`

**Issue:** `exec(code, globs)` where `globs` does not contain a `"__builtins__"` key causes Python to automatically inject the full `builtins` module into `globs`. This means any `.star` script can call `__import__("os").system("rm -rf /")`, `open(...)`, `eval(...)`, etc. The sandbox intent is to expose only `sys.*` namespaces, but the current implementation exposes all of Python's standard library via `__builtins__`.

```python
# In a .star script — this works today:
__import__("os").system("id")  # executes arbitrary shell command
open("/etc/passwd").read()      # reads arbitrary files
```

**Fix:** Explicitly restrict builtins:

```python
globs = {"sys": self._sys, "__builtins__": {}}
```

An empty dict removes all builtins. If specific builtins are needed (e.g., `len`, `range`, `print`, `str`, `int`, `float`, `bool`, `list`, `dict`), enumerate them explicitly:

```python
_SAFE_BUILTINS = {"len": len, "range": range, "print": print, "str": str,
                  "int": int, "float": float, "bool": bool, "list": list,
                  "dict": dict, "all": all, "any": any, "None": None,
                  "True": True, "False": False}
globs = {"sys": self._sys, "__builtins__": _SAFE_BUILTINS}
```

This must also be applied when executing lib files (line 70).

---

## Warnings

### WR-01: `cli.py` (sysscript) does not catch `FileNotFoundError` or `PermissionError`

**File:** `tools/adsops/src/adsops/sysscript/cli.py:16-24`

**Issue:** `runner.run()` calls `pathlib.Path.read_text()` (lines 60, 67 in runner.py). If `script_path` does not exist or is not readable, Python raises `FileNotFoundError` or `PermissionError`. These are not caught in `run_cmd()`, so they bubble up as unhandled exceptions with a Python traceback instead of a clean error message. Only `NotImplementedError` and `ValueError` are caught.

**Fix:**

```python
except (FileNotFoundError, PermissionError) as e:
    typer.echo(f"ERROR: Cannot read script: {e}", err=True)
    raise typer.Exit(1)
```

---

### WR-02: `cli.py` (sysscript) does not catch `SyntaxError` from `compile()`

**File:** `tools/adsops/src/adsops/sysscript/cli.py:16-24` / `tools/adsops/src/adsops/sysscript/runner.py:70,74`

**Issue:** `compile()` raises `SyntaxError` when the `.star` script contains invalid Python-compatible syntax. This also propagates as an unhandled traceback. For a tool intended to provide clean operator feedback, this is a quality gap.

**Fix:** Add to the except chain in `run_cmd()`:

```python
except SyntaxError as e:
    typer.echo(f"ERROR: Script syntax error: {e}", err=True)
    raise typer.Exit(1)
```

---

### WR-03: Recursive `load()` in lib files is silently dropped, not rejected

**File:** `tools/adsops/src/adsops/sysscript/runner.py:69`

**Issue:** The comment says "recursive resolution not needed for MVP" and uses `_LOAD_PATTERN.sub("", lib_src)` to strip nested `load()` calls from lib files. This is silent: if a lib file has a `load()` that is genuinely needed for its logic to work (e.g., `lib/k3s.star` loading `lib/host.star`), that load is silently dropped and the lib will fail at runtime with a `NameError`. The operator gets no warning that a required dependency was ignored.

**Fix:** Either raise a `ValueError` if any lib file contains `load()` calls (fail-fast), or implement recursive resolution. Silent dropping is the worst option because it produces mysterious `NameError`s at script execution time:

```python
if _LOAD_PATTERN.search(lib_src):
    raise ValueError(
        f"Nested load() in lib file {lib_path} is not supported"
    )
```

---

### WR-04: `stats.star` — `request_count` may be `None` and is printed without guard

**File:** `sysscripts/services/changes-api/stats.star:29`

**Issue:** `request_count` is initialized to `None` and only assigned if a line starting with `http_requests_total` is found. If the metrics endpoint does not include that metric (e.g., endpoint is down, format changed), `print("request_count:", request_count)` prints `request_count: None`. This is misleading — it looks like a successful read with a null value rather than a missing metric. The same applies to `latency_sum` and `latency_count` though those are guarded in the `latency_avg` computation.

**Fix:**

```python
print("request_count:", request_count if request_count is not None else "N/A (metric not found)")
```

Or validate that all expected metrics were found before printing results.

---

### WR-05: `_find_sysscripts_root` matches any ancestor named `sysscripts`, including deeper nesting — ambiguous behavior

**File:** `tools/adsops/src/adsops/sysscript/runner.py:26-31`

**Issue:** `pathlib.Path.parents` iterates from nearest ancestor to root. The method returns the *first* ancestor named `sysscripts`. If the filesystem has a path like `/home/user/sysscripts/nested/sysscripts/services/foo.star`, the inner `sysscripts` is returned as root. This is probably the intended behavior, but it means the sandbox root can vary depending on how deeply a script is nested — a script at `/tmp/sysscripts/evil.star` would find `/tmp/sysscripts` as its own root, execute freely, and satisfy its own sandbox (see CR-01 for the entry-point check gap this interacts with). The auto-discovery design fundamentally ties sandbox scope to filesystem structure, which is fragile.

**Fix:** Accept an explicit `sysscripts_root` parameter in `SysscriptRunner.__init__()` as the authoritative sandbox root, using auto-discovery only as a fallback. This lets callers (especially the CLI and tests) pin the root to a known-safe path:

```python
def __init__(self, sys_global=None, sysscripts_root: str = None):
    self._sys = sys_global if sys_global is not None else MockSys()
    self._root_override = pathlib.Path(sysscripts_root).resolve() if sysscripts_root else None
```

---

## Info

### IN-01: MockSys docstring and inline comment disagree on namespace count

**File:** `tools/adsops/src/adsops/sysscript/mock.py:39`

**Issue:** The inline comment says "All 14 namespaces from sysscript.go (VERIFIED)" but 15 namespaces are actually instantiated (`net`, `exec`, `fs`, `alerts`, `security`, `events`, `packages`, `containers`, `config`, `yaml`, `json`, `ini`, `services`, `proc`, `k3s`). This is audit drift — the comment will mislead future readers auditing namespace coverage.

**Fix:** Update comment to "15 namespaces" or add a count assertion to the class body.

---

### IN-02: `adsops/cli.py` silently swallows `ImportError` for all sub-apps with no diagnostic

**File:** `tools/adsops/src/adsops/cli.py:6-34`

**Issue:** Each sub-app registration is wrapped in a bare `except ImportError: pass`. This is intentional for optional wave-based loading, but it means a broken import (e.g., a module that exists but has a syntax error or a broken transitive import) is silently discarded and the sub-app simply does not appear in the CLI. This will be confusing when a module is present but broken — the operator sees no `sysscript` subcommand with no explanation.

**Fix:** Consider logging at debug level or printing a warning in non-quiet mode:

```python
except ImportError as e:
    if os.environ.get("ADSOPS_DEBUG"):
        typer.echo(f"[debug] sysscript sub-app not loaded: {e}", err=True)
```

This preserves the optional-loading design while providing a diagnostic escape hatch.

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
