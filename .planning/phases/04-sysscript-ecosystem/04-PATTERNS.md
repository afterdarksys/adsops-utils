# Phase 4: Sysscript Ecosystem - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 13 new/modified files
**Analogs found:** 11 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/adsops/src/adsops/sysscript/runner.py` | service | transform | `tools/adsops/src/adsops/sysscript/mock.py` | role-match |
| `tools/adsops/src/adsops/sysscript/cli.py` | controller | request-response | `tools/adsops/src/adsops/infractl/cli.py` | exact |
| `tools/adsops/src/adsops/cli.py` (modify) | config | request-response | `tools/adsops/src/adsops/cli.py` | exact (self) |
| `sysscripts/lib/host.star` | utility | transform | `sysscripts/services/statsagent/health.star` (to be created) | none — see RESEARCH.md Pattern 3 |
| `sysscripts/lib/docker.star` | utility | transform | none | none |
| `sysscripts/lib/k3s.star` | utility | transform | none | none |
| `sysscripts/services/statsagent/health.star` | service | request-response | `sysscripts/services/changes-api/health.star` (sibling, to be created) | none — see RESEARCH.md Pattern 3 |
| `sysscripts/services/changes-api/health.star` | service | request-response | none | none — see RESEARCH.md Pattern 3 |
| `sysscripts/services/changes-api/stats.star` | service | request-response | none | none — see RESEARCH.md Patterns 3 & 5 |
| `tools/adsops/tests/sysscripts/__init__.py` | config | — | `tools/adsops/tests/__init__.py` | exact |
| `tools/adsops/tests/sysscripts/test_host_star.py` | test | transform | `tools/adsops/tests/test_mocksys.py` | role-match |
| `tools/adsops/tests/sysscripts/test_docker_star.py` | test | transform | `tools/adsops/tests/test_mocksys.py` | role-match |
| `tools/adsops/tests/sysscripts/test_k3s_star.py` | test | transform | `tools/adsops/tests/test_mocksys.py` | role-match |
| `tools/adsops/tests/sysscripts/test_statsagent_health.py` | test | request-response | `tools/adsops/tests/test_mocksys.py` | role-match |
| `tools/adsops/tests/sysscripts/test_changes_api_health.py` | test | request-response | `tools/adsops/tests/test_mocksys.py` | role-match |
| `tools/adsops/tests/sysscripts/test_changes_api_stats.py` | test | request-response | `tools/adsops/tests/test_mocksys.py` | role-match |

---

## Pattern Assignments

### `tools/adsops/src/adsops/sysscript/runner.py` (service, transform)

**Analog:** `tools/adsops/src/adsops/sysscript/mock.py`

**Imports pattern** (`mock.py` lines 1-2):
```python
from typing import Any, Callable
```

Extend to runner.py imports (from RESEARCH.md Pattern 1):
```python
import os
import re
import pathlib
from adsops.sysscript.mock import MockSys
```

**Core pattern** — `exec()`-based runner (RESEARCH.md Pattern 1, lines 219-262 of 04-RESEARCH.md):
```python
_LOAD_PATTERN = re.compile(
    r"""load\(\s*["']([^"']+)["'](?:\s*,\s*["']\w+["'])*\s*\)\n?"""
)

class SysscriptRunner:
    def __init__(self, sys_global=None):
        self._sys = sys_global if sys_global is not None else MockSys()

    def _find_sysscripts_root(self, script_path: pathlib.Path) -> pathlib.Path:
        """Walk ancestors to find nearest directory named 'sysscripts' (D-07)."""
        for parent in script_path.parents:
            if parent.name == "sysscripts":
                return parent
        raise ValueError(f"No 'sysscripts/' ancestor found for: {script_path}")

    def _resolve_load(self, load_path: str, script_dir: pathlib.Path,
                      sysscripts_root: pathlib.Path) -> pathlib.Path:
        """Resolve a load() path and enforce sandbox (D-05, D-06)."""
        resolved = (script_dir / load_path).resolve()
        root = sysscripts_root.resolve()
        if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
            raise ValueError(f"load({load_path!r}): path traversal not allowed")
        return resolved

    def run(self, script_path: str) -> dict:
        """Execute a .star file and return its final globals dict."""
        path = pathlib.Path(script_path).resolve()
        root = self._find_sysscripts_root(path)
        content = path.read_text()

        globs = {"sys": self._sys}

        # Pre-execute load() targets (in order found)
        for m in _LOAD_PATTERN.finditer(content):
            lib_path = self._resolve_load(m.group(1), path.parent, root)
            lib_src = lib_path.read_text()
            lib_src_clean = _LOAD_PATTERN.sub("", lib_src)
            exec(compile(lib_src_clean, str(lib_path), "exec"), globs)

        # Strip load() from main script then execute
        main_src = _LOAD_PATTERN.sub("", content)
        exec(compile(main_src, str(path), "exec"), globs)
        return globs
```

**Error handling pattern** — follow MockNamespace's pattern of raising `NotImplementedError` with descriptive messages (`mock.py` lines 15-22):
```python
if fixture is None:
    raise NotImplementedError(
        f"MockSys: no fixture for '{key}'. "
        f"Pass fixtures={{'{key}': <return_value>}} to MockSys()"
    )
```

**Security — path traversal guard** (both conditions required, D-06):
```python
if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
    raise ValueError(f"load({load_path!r}): path traversal not allowed")
```

---

### `tools/adsops/src/adsops/sysscript/cli.py` (controller, request-response)

**Analog:** `tools/adsops/src/adsops/infractl/cli.py`

**Imports pattern** (`infractl/cli.py` lines 11-15):
```python
import typer

app = typer.Typer(
    help="Manage remote Docker and k3s infrastructure",
    no_args_is_help=True,
)
```

**Core pattern — single command sub-app** (adapt from infractl pattern, RESEARCH.md Pattern 4):
```python
import typer

app = typer.Typer(help="Run and manage sysscripts", no_args_is_help=True)

@app.command("run")
def run_cmd(script: str = typer.Argument(..., help="Path to .star script")) -> None:
    """Execute a .star script locally with empty MockSys (D-04)."""
    from adsops.sysscript.runner import SysscriptRunner
    runner = SysscriptRunner()  # empty MockSys — calls raise NotImplementedError
    try:
        runner.run(script)
    except NotImplementedError as e:
        typer.echo(f"Script needs fixture: {e}", err=True)
        raise typer.Exit(1)
```

**Command arguments pattern** — `typer.Argument` with help string (from `infractl/cli.py` lines 33, 58, 132):
```python
host: str = typer.Argument(..., help="Remote host")
container: str = typer.Argument(..., help="Container name or ID")
```

**Error output pattern** (`infractl/cli.py` lines 43, 69):
```python
typer.echo(f"ERROR: {item}", err=True)
raise typer.Exit(1)
```

---

### `tools/adsops/src/adsops/cli.py` (modify — add sysscript registration)

**Analog:** Self — `tools/adsops/src/adsops/cli.py`

**try/except registration pattern** (`cli.py` lines 6-27 — full `_register()` body):
```python
def _register():
    """Register sub-apps. Uses try/except so modules built in later waves
    are picked up automatically once they exist."""
    try:
        from adsops.hostctl.cli import app as hostctl_app
        app.add_typer(hostctl_app, name="hostctl")
    except ImportError:
        pass

    try:
        from adsops.infractl.cli import app as infractl_app
        app.add_typer(infractl_app, name="infractl")
    except ImportError:
        pass

    try:
        from adsops.stats.cli import app as stats_app
        app.add_typer(stats_app, name="stats")
    except ImportError:
        pass
```

**Add after existing registrations:**
```python
    try:
        from adsops.sysscript.cli import app as sysscript_app
        app.add_typer(sysscript_app, name="sysscript")
    except ImportError:
        pass
```

---

### `sysscripts/lib/host.star` (utility, transform)

**Analog:** None in codebase. Use RESEARCH.md Pattern 3 (sys namespace usage).

**sys namespace pattern for host helpers** (RESEARCH.md Pattern 3):
```python
# sys.exec.run returns (exit_code, stdout, stderr)
# sys.config.get returns a string value for the given key
# lib files define named functions; callers load them via load("../../lib/host.star", "host_info")
# Return dicts (Claude's Discretion: dicts over strings for structured data)

def host_info():
    code, out, err = sys.exec.run("hostname")
    hostname = out.strip() if code == 0 else "unknown"
    code2, out2, err2 = sys.exec.run("uname -s")
    os_name = out2.strip() if code2 == 0 else "unknown"
    return {"hostname": hostname, "os": os_name}
```

**load() statement syntax** (RESEARCH.md Pattern 2):
```python
load("../../lib/host.star", "host_info")
```

---

### `sysscripts/lib/docker.star` (utility, transform)

**Analog:** None in codebase. Use RESEARCH.md Pattern 3.

**sys namespace pattern for Docker helpers:**
```python
# sys.containers.list() returns list of container dicts
# sys.containers.stats(name) returns stats dict
def container_list():
    return sys.containers.list()

def container_stats(name):
    return sys.containers.stats(name)
```

---

### `sysscripts/lib/k3s.star` (utility, transform)

**Analog:** None in codebase. Use RESEARCH.md Pattern 3.

**sys namespace pattern for k3s helpers:**
```python
# sys.k3s.nodes() returns list of node dicts
# sys.k3s.pods() returns list of pod dicts
def k3s_node_list():
    return sys.k3s.nodes()

def k3s_pod_list():
    return sys.k3s.pods()
```

---

### `sysscripts/services/statsagent/health.star` (service, request-response)

**Analog:** None — first service script. Use RESEARCH.md Pattern 3.

**Core pattern** (D-08 adapted for statsagent, RESEARCH.md Pattern 3):
```python
# No load() needed if no lib helpers are used; add if host_info is needed
base_url = sys.config.get("statsagent_url")
resp = sys.net.http_get(base_url + "/health")
healthy = (resp["status_code"] == 200)
```

**Note:** `sys.net.http_get` returns `{"status_code": int, "body": str}` — verified from mock.py + RESEARCH.md.

---

### `sysscripts/services/changes-api/health.star` (service, request-response)

**Analog:** None — use RESEARCH.md Pattern 3 (D-08, D-10).

**Core pattern:**
```python
base_url = sys.config.get("changes_api_url")
resp = sys.net.http_get(base_url + "/health")
healthy = (resp["status_code"] == 200)
```

---

### `sysscripts/services/changes-api/stats.star` (service, request-response)

**Analog:** None — use RESEARCH.md Patterns 3 & 5 (D-09, D-10).

**Core pattern — Prometheus text parsing** (RESEARCH.md Code Examples):
```python
base_url = sys.config.get("changes_api_url")
body = sys.net.http_get(base_url + "/metrics")["body"]

request_count = None
latency_sum = None
latency_count = None

for line in body.split("\n"):
    if line.startswith("#") or line == "":
        continue
    if line.startswith("http_requests_total{") or line == "http_requests_total":
        parts = line.split(" ")
        if len(parts) >= 2:
            request_count = parts[-1]
    if line.startswith("http_request_duration_seconds_sum"):
        latency_sum = line.split(" ")[-1]
    if line.startswith("http_request_duration_seconds_count"):
        latency_count = line.split(" ")[-1]

print("request_count:", request_count)
print("latency_avg_seconds:", float(latency_sum) / float(latency_count) if latency_count and float(latency_count) > 0 else 0)
```

---

### `tools/adsops/tests/sysscripts/__init__.py` (config)

**Analog:** `tools/adsops/tests/__init__.py` — empty file (1 line, blank).

Copy exactly: empty file to mark directory as a Python package.

---

### `tools/adsops/tests/sysscripts/test_*.py` — all six test files (test, request-response/transform)

**Analog:** `tools/adsops/tests/test_mocksys.py`

**Imports pattern** (`test_mocksys.py` lines 1-2):
```python
import pytest
from adsops.sysscript.mock import MockSys, MockNamespace
```

**Extended for sysscript runner tests** (RESEARCH.md Pattern 5):
```python
import pytest
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

SCRIPT = "sysscripts/services/changes-api/health.star"  # adjust per test file

def make_runner(fixtures: dict) -> SysscriptRunner:
    return SysscriptRunner(sys_global=MockSys(fixtures))
```

**Test structure pattern** (`test_mocksys.py` lines 11-29 — static fixture + callable fixture patterns):
```python
def test_health_check_passes_on_200():
    runner = make_runner({
        "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
        "net.http_get": {"status_code": 200, "body": ""},
    })
    result = runner.run(SCRIPT)
    assert result.get("healthy") == True

def test_health_check_fails_on_non_200():
    runner = make_runner({
        "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
        "net.http_get": {"status_code": 503, "body": ""},
    })
    result = runner.run(SCRIPT)
    assert result.get("healthy") == False
```

**Callable fixture pattern** (use lambda for methods that receive arguments — RESEARCH.md Pitfall 5):
```python
# CORRECT — callable fixture for parameterized method:
"config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None

# WRONG — static fixture ignores all keys:
"config.get": "http://localhost:8080"
```

**Missing fixture assertion pattern** (`test_mocksys.py` lines 25-29):
```python
with pytest.raises(NotImplementedError, match="no fixture for 'net.http_get'"):
    sys.net.http_get("url")
```

---

## Shared Patterns

### MockSys Fixture Dict Construction
**Source:** `tools/adsops/src/adsops/sysscript/mock.py` (MockNamespace.__getattr__, lines 11-22)
**Apply to:** All test files in `tests/sysscripts/`

```python
# MockNamespace calls fixture(*args, **kwargs) if callable, else returns fixture directly
# Pattern: use callable for any method that receives arguments (e.g., config.get(key))
# Pattern: use static dict/string for methods whose return value is fixed (e.g., net.http_get)
MockSys({
    "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
    "net.http_get": {"status_code": 200, "body": ""},
})
```

### try/except Sub-App Registration
**Source:** `tools/adsops/src/adsops/cli.py` (lines 6-27)
**Apply to:** Modification of `cli.py` to add sysscript sub-app

```python
try:
    from adsops.sysscript.cli import app as sysscript_app
    app.add_typer(sysscript_app, name="sysscript")
except ImportError:
    pass
```

### Typer Error Output and Exit
**Source:** `tools/adsops/src/adsops/infractl/cli.py` (lines 43-44, 69-70)
**Apply to:** `sysscript/cli.py`

```python
typer.echo(f"ERROR: {item}", err=True)
raise typer.Exit(1)
```

### sys Namespace Attribute Access in .star Scripts
**Source:** RESEARCH.md Pattern 3 (D-02; verified against mock.py and RESEARCH.md)
**Apply to:** All `.star` files

```python
# sys is a Python object injected as a global — NOT loaded via load()
# Access: sys.<namespace>.<method>(args)
base_url = sys.config.get("changes_api_url")   # sys.config is MockNamespace("config", fixtures)
resp = sys.net.http_get(base_url + "/health")   # returns {"status_code": int, "body": str}
```

### Path Traversal Guard (sandbox enforcement)
**Source:** RESEARCH.md Pattern 1 + Pitfall 6 (D-06)
**Apply to:** `runner.py` `_resolve_load()` method

```python
# Both conditions are required (off-by-one: resolved == root is the edge case)
if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
    raise ValueError(f"load({load_path!r}): path traversal not allowed")
```

---

## No Analog Found

Files with no close match in the codebase (use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `sysscripts/lib/host.star` | utility | transform | No Starlark files exist yet; use RESEARCH.md Pattern 3 for sys.exec.run() usage |
| `sysscripts/lib/docker.star` | utility | transform | No Starlark files exist yet; use RESEARCH.md Pattern 3 for sys.containers.*() usage |
| `sysscripts/lib/k3s.star` | utility | transform | No Starlark files exist yet; use RESEARCH.md Pattern 3 for sys.k3s.*() usage |
| `sysscripts/services/statsagent/health.star` | service | request-response | First service script; use RESEARCH.md Pattern 3 + D-08 |
| `sysscripts/services/changes-api/health.star` | service | request-response | No Starlark service scripts exist; use RESEARCH.md Pattern 3 + D-08, D-10 |
| `sysscripts/services/changes-api/stats.star` | service | request-response | Prometheus parsing is unique; use RESEARCH.md Code Examples section |

---

## Key Constraints Carried Forward

1. **No new PyPI packages** — `starlark-py` does not exist; runner uses Python stdlib `exec()` only. `pyproject.toml` is unchanged.
2. **starlark-go must NOT be used as runner** — verified SIGSEGV on callable injection; no load() support.
3. **All load() targets exec'd into one shared globals dict** — not isolated per-lib; broader than strict Starlark but correct for exec() runner.
4. **sys injected as Python object, not dict** — `sys.net.http_get()` requires attribute access; dict injection would break all scripts.
5. **Test SCRIPT paths are relative to cwd** — runner uses `pathlib.Path(script_path).resolve()` which handles both absolute and relative paths at call site.

## Metadata

**Analog search scope:** `tools/adsops/src/adsops/`, `tools/adsops/tests/`
**Files scanned:** 6 (mock.py, cli.py, infractl/cli.py, test_mocksys.py, test_cli.py, pyproject.toml)
**Pattern extraction date:** 2026-05-04
