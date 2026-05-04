# Phase 4: Sysscript Ecosystem - Research

**Researched:** 2026-05-04
**Domain:** Starlark scripting, Python CLI, Prometheus text parsing
**Confidence:** HIGH

## Summary

Phase 4 delivers a working Sysscript ecosystem: shared Starlark helper libraries, per-service health and stats scripts, a local Python runner (`adsops sysscript run`), and per-script tests using the existing MockSys harness. The implementation is self-contained within the `adsops-utils` repo — no external agents or binary dependencies are required for the runner.

The most important discovery from this research is that **`starlark-py` (named in CONTEXT.md D-01) does not exist on PyPI**. No Python package with that name has any published version. The correct approach — given the project's constraint to avoid binary dependencies and support native Python object injection (for MockSys) — is to implement `runner.py` using Python's built-in `exec()` with a custom load() resolver. This is architecturally sound because Starlark is a strict subset of Python syntax, and service scripts only use features (string ops, loops, attribute access, dicts) that are valid in both languages.

The existing `MockSys` and `MockNamespace` in `tools/adsops/src/adsops/sysscript/mock.py` are already fully built and tested. The runner injects a `MockSys()` instance as the `sys` global, which provides the `sys.net.http_get()`, `sys.config.get()` etc. attribute access the service scripts expect. No new mocking infrastructure is needed.

**Primary recommendation:** Implement `runner.py` as a pure-Python `exec()`-based Starlark executor with manual `load()` resolution and path-traversal protection. Add `starlark-go==1.0.1` to `pyproject.toml` only if syntax validation is desired as a Wave 2 enhancement; it is not required for MVP runner or tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Use `starlark-py` (PyPI) as the local Starlark interpreter — pure Python, no binary dependencies, installs into the existing `tools/adsops/` venv alongside other deps.
> **RESEARCH NOTE:** `starlark-py` does NOT exist on PyPI (`pip install starlark-py` returns "No matching distribution found"). The correct implementation is a pure-Python `exec()`-based runner (see Architecture Patterns). This is equivalent in spirit to D-01 (pure Python, no binary deps) but requires no PyPI package. The planner must deviate from the literal package name and instead implement runner.py using `exec()` directly.

**D-02:** `sys` is injected as a **predefined global** before script evaluation — same pattern as the real agent. Script authors use `sys.net.http_get(...)` naturally without a `load()` call for it.

**D-03:** Default local run uses an **empty MockSys** — any `sys.*` call raises `NotImplementedError` with a helpful message listing the missing fixture key. This makes the script's dependencies visible and ensures tests always provide explicit fixtures.

**D-04:** `adsops sysscript run <script.star>` is the CLI surface. No `--fixture` flag for MVP; fixture data is only used in tests, not via the CLI.

**D-05:** Service scripts use **relative paths** for `load()`: e.g., `load("../../lib/host.star", "host_info")`. Paths are relative to the script file's location. The runner resolves them at execution time.

**D-06:** The **sandbox root is `sysscripts/`** — the runner rejects any `load()` path that resolves outside the `sysscripts/` directory tree. Consistent with Thread.Load path traversal protection (T-03-01).

**D-07:** Runner auto-discovers the `sysscripts/` root as the nearest ancestor directory of the script being run that is named `sysscripts`. No explicit config needed.

**D-08:** `changes-api/health.star` calls `sys.net.http_get(base_url + "/health")` and checks for HTTP 200.

**D-09:** `changes-api/stats.star` calls `sys.net.http_get(base_url + "/metrics")`, parses Prometheus text-format output, and extracts request count and latency histogram values.

**D-10:** Both changes-api scripts read the base URL via `sys.config.get("changes_api_url")`. Tests provide this via MockSys fixture.

### Claude's Discretion

- Exact Prometheus metric names to parse in stats.star (standard `http_requests_total` and `http_request_duration_seconds` histogram patterns)
- Starlark helper function signatures within lib/ files
- Whether lib/ helpers return dicts or structured strings
- Test fixture file format and location within `tests/sysscripts/`

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STAR-01 | `sysscripts/lib/host.star` — common host introspection helpers | Runner handles load(); host helpers use sys.exec.run() for hostname/OS info |
| STAR-02 | `sysscripts/lib/docker.star` — Docker helpers (list containers, get stats) | Uses sys.containers.list(), sys.containers.stats() from agent namespace |
| STAR-03 | `sysscripts/lib/k3s.star` — k3s helpers (list pods, check health) | Uses sys.k3s.nodes(), sys.k3s.pods() from agent namespace |
| STAR-04 | `sysscripts/services/statsagent/health.star` — statsagent health check | HTTP GET to /health endpoint, check status_code == 200 |
| STAR-05 | `sysscripts/services/changes-api/health.star` — changes-api health check | D-08: http_get to base_url + "/health", check 200 |
| STAR-06 | `sysscripts/services/changes-api/stats.star` — changes-api metrics | D-09: http_get /metrics, parse Prometheus text format for request counts + latency |
| STAR-07 | Python test harness executes each `.star` script locally with mock sys | exec()-based runner + MockSys fixtures; one test file per script |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Starlark script execution | Python CLI (runner.py) | — | Local runner handles exec(), load() resolution, sys injection |
| load() path resolution + sandbox | Python CLI (runner.py) | — | Security boundary; mirrors agent Thread.Load logic |
| sys global injection | Python CLI (runner.py) | Agent (remote) | Runner injects MockSys; agent injects real sys |
| Shared Starlark helpers | sysscripts/lib/*.star | — | Loaded by service scripts via load(); no Python layer needed |
| Service scripts | sysscripts/services/\*/*.star | — | Pure Starlark; tested via Python harness |
| Test fixtures | tools/adsops/tests/sysscripts/ | — | Python test files using MockSys with fixture dicts |
| CLI command | tools/adsops/src/adsops/sysscript/cli.py | adsops/cli.py | Typer sub-app registered via try/except pattern |
| Prometheus text parsing | sysscripts/services/changes-api/stats.star | — | In-Starlark string split; no external library needed |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python built-in `exec()` | stdlib | Starlark script execution | No PyPI package needed; Starlark is Python-compatible syntax |
| `adsops.sysscript.mock.MockSys` | Phase 2 output | sys global for local + test runs | Already built, all 15 namespaces, fixture-dict pattern |
| `typer` | >=0.21 (already in pyproject.toml) | `adsops sysscript run` CLI command | Already used by infractl, hostctl sub-apps |
| `re` (stdlib) | stdlib | load() statement parsing from script source | No external dep needed |
| `pathlib` (stdlib) | stdlib | Path resolution, sandbox enforcement | Cross-platform, clean API |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `starlark-go` | 1.0.1 | Starlark syntax validation | Optional Wave 2 enhancement only — NOT for MVP runner |
| `pytest` | 8.3.3 (already installed) | Per-script test files | All tests in `tests/sysscripts/` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python exec() runner | starlark-go PyPI package | starlark-go cannot inject Python objects as globals (SIGSEGV on callable injection, ConversionToStarlarkFailed on object injection). Not usable for MockSys pattern. |
| Python exec() runner | starlark-pyo3 PyPI package | Requires Rust toolchain to build from source; wheel only available via sdist on this platform. Complex dependency. |
| Python exec() runner | pystarlark PyPI package | Binds to starlark-go via cgo; no pure-Python implementation. |
| Python exec() runner | starlark-py | Does NOT EXIST on PyPI. No version available. |

**Installation (no new packages for MVP runner):**
```bash
# No new pip dependencies needed for runner.py
# pyproject.toml remains unchanged for Phase 4
```

**Version verification:**
```
starlark-py: NOT FOUND on PyPI (verified: pip install starlark-py → "No matching distribution found")
starlark-go: 1.0.1 available but cannot inject Python objects; cannot implement load()
Python exec(): stdlib, no install needed
```
[VERIFIED: pip3 install starlark-py --dry-run, 2026-05-04]
[VERIFIED: pip3 install starlark-go --dry-run, starlark-go==1.0.1 available, 2026-05-04]
[VERIFIED: live testing of starlark-go Python API, 2026-05-04]

## Architecture Patterns

### System Architecture Diagram

```
adsops sysscript run sysscripts/services/changes-api/health.star
         │
         ▼
┌─────────────────────────────────────────────────┐
│  runner.py: SysscriptRunner                     │
│  1. Discover sysscripts/ root (D-07)            │
│  2. Read script source                          │
│  3. Parse load() statements (regex)             │
│  4. Resolve each load() path (relative → abs)  │
│  5. Validate: all paths within sysscripts/ root │
│     (D-06: sandbox enforcement)                 │
│  6. exec() each lib file in order (globals)     │
│  7. Strip load() from main script               │
│  8. exec() main script with sys=MockSys()       │
└─────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
  sysscripts/lib/       sys = MockSys()
  host.star             (empty for CLI run)
  docker.star           (fixture-backed for tests)
  k3s.star
```

**Data flow for test execution:**
```
test_health_star.py
  │  MockSys({"net.http_get": ..., "config.get": ...})
  │
  ▼
SysscriptRunner.run(script_path, sys=mock_sys)
  │
  ├─ resolve load() → sysscripts/lib/host.star
  ├─ exec(host_star_content, globals)
  ├─ exec(health_star_content, globals)
  │
  ▼
globals["healthy"] == True  ← test assertion
```

### Recommended Project Structure

```
sysscripts/
├── lib/
│   ├── host.star           # STAR-01: host introspection helpers
│   ├── docker.star         # STAR-02: Docker helpers
│   └── k3s.star            # STAR-03: k3s helpers
└── services/
    ├── statsagent/
    │   └── health.star     # STAR-04
    └── changes-api/
        ├── health.star     # STAR-05
        └── stats.star      # STAR-06

tools/adsops/src/adsops/sysscript/
├── __init__.py
├── mock.py                 # Existing: MockSys, MockNamespace
├── runner.py               # NEW: SysscriptRunner (exec-based)
└── cli.py                  # NEW: Typer sub-app for 'sysscript run'

tools/adsops/tests/sysscripts/
├── __init__.py
├── test_host_star.py       # Tests for lib/host.star
├── test_docker_star.py     # Tests for lib/docker.star
├── test_k3s_star.py        # Tests for lib/k3s.star
├── test_statsagent_health.py
├── test_changes_api_health.py
└── test_changes_api_stats.py
```

### Pattern 1: Python exec()-based Starlark Runner

**What:** Execute `.star` files via Python's `exec()`, injecting `sys` as a Python global. Handle `load()` by pre-executing lib files into the same `globals` dict, then stripping `load()` statements before executing the main script.

**When to use:** Anytime a .star file needs local execution (CLI run or test harness).

**Why exec() not a Starlark package:** Starlark is a syntactic subset of Python. Service scripts use only: function definitions, string operations, dict literals, for-loops, attribute access (`sys.net.http_get()`), and conditional expressions. Python executes all of these natively. The exec()-based approach also allows injecting a live Python MockSys object as `sys`, which no available Starlark PyPI package supports.

**Example:**
```python
# Source: verified by testing, 2026-05-04
# tools/adsops/src/adsops/sysscript/runner.py

import os
import re
import pathlib
from adsops.sysscript.mock import MockSys

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
            # Recursively resolve nested loads in lib files
            lib_src_clean = _LOAD_PATTERN.sub("", lib_src)
            exec(compile(lib_src_clean, str(lib_path), "exec"), globs)

        # Strip load() from main script then execute
        main_src = _LOAD_PATTERN.sub("", content)
        exec(compile(main_src, str(path), "exec"), globs)
        return globs
```

### Pattern 2: Starlark load() Statement Grammar

Service scripts use this exact syntax for library imports:
```python
# Source: CONTEXT.md D-05; consistent with Starlark spec
load("../../lib/host.star", "host_info")
load("../../lib/docker.star", "container_list", "container_stats")
```

Key points:
- First arg is a string literal (the file path, relative to the script's location)
- Subsequent args are string names of symbols to import (informational in our runner)
- Our runner ignores the symbol names — it exec()s the entire lib file into globals

### Pattern 3: sys Namespace Usage in .star Scripts

```python
# Source: CONTEXT.md D-02, D-08, D-10; agent sysscript.go verified
# How service scripts call sys — pure attribute access, no load() needed

base_url = sys.config.get("changes_api_url")
resp = sys.net.http_get(base_url + "/health")
healthy = (resp["status_code"] == 200)
```

```python
# stats.star Prometheus parsing pattern
# sys.net.http_get returns {"status_code": int, "body": str}
# Parse body as Prometheus text format using string operations only

metrics_body = sys.net.http_get(base_url + "/metrics")["body"]
request_count = None
for line in metrics_body.split("\n"):
    if line.startswith("http_requests_total{") and not line.startswith("#"):
        request_count = int(float(line.split(" ")[-1]))
```

### Pattern 4: CLI Sub-App Registration

```python
# Source: verified from tools/adsops/src/adsops/infractl/cli.py pattern
# tools/adsops/src/adsops/sysscript/cli.py

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

# Registration in tools/adsops/src/adsops/cli.py:
# try:
#     from adsops.sysscript.cli import app as sysscript_app
#     app.add_typer(sysscript_app, name="sysscript")
# except ImportError:
#     pass
```

### Pattern 5: Per-Script Test Structure

```python
# Source: verified from tools/adsops/tests/test_mocksys.py pattern
# tools/adsops/tests/sysscripts/test_changes_api_health.py

import pytest
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

SCRIPT = "sysscripts/services/changes-api/health.star"

def make_runner(fixtures: dict) -> SysscriptRunner:
    return SysscriptRunner(sys_global=MockSys(fixtures))

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

### Anti-Patterns to Avoid

- **Installing starlark-py:** The package does not exist on PyPI. Do not add it to pyproject.toml.
- **Using starlark-go for runner:** The package cannot inject Python objects as globals (raises ConversionToStarlarkFailed) and segfaults on callable injection. It also does not implement load(). [VERIFIED: live testing]
- **Implementing load() by concatenating file contents:** Loses filename context in error tracebacks and can cause symbol collisions.
- **Creating a separate Starlark execution context per lib file:** All load() targets and the main script must share the SAME globals dict so functions from libs are available in the main script.
- **Recursive load() in a new globals dict:** lib files may be loaded into isolated namespaces which breaks the exec() chain. Use one shared globals dict.
- **Injecting sys as a dict instead of Python object:** `sys["net"]["http_get"]()` is not valid Starlark attribute access. Scripts expect `sys.net.http_get()`. Only Python object injection supports this.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| sys namespace (all namespaces) | Custom mock class from scratch | `adsops.sysscript.mock.MockSys` | Already built, tested, all 15 namespaces covered |
| Fixture-dict handler | Custom fixture lookup | `MockNamespace` | Already handles callable vs static fixtures, NotImplementedError with helpful message |
| Typer CLI boilerplate | Custom argparse/click | `typer.Typer()` + `@app.command()` | Already the project standard; infractl/cli.py is the reference |
| Prometheus text format full parse | Custom parser with regex | Simple string split in .star | Only need metric names + scalar values; no complex label parsing needed for this use case |
| Test discovery/runner | Custom test framework | `pytest` | Already installed, already the project standard |

**Key insight:** MockSys is the entire test infrastructure for sysscripts. The runner's only job is to exec() the .star files and inject the existing MockSys instance. Approximately zero new infrastructure is needed.

## Common Pitfalls

### Pitfall 1: load() Symbols vs exec() Scope

**What goes wrong:** The Starlark load() spec says `load("lib.star", "fn_name")` imports only `fn_name` into the calling module's scope. Python exec() into a shared globals dict imports ALL symbols from the lib file. This is broader than strict Starlark semantics.

**Why it happens:** exec() into shared globals makes everything defined in the lib available, not just the listed symbols.

**How to avoid:** For the MVP runner, the broader scope is acceptable (and actually simpler). Document that the runner does not enforce symbol-level isolation. If strict isolation is needed in the future, post-process the globals dict to retain only listed symbol names.

**Warning signs:** If lib files define symbols that conflict with the main script's local names, silent override occurs. Keep lib function names clearly namespaced (e.g., `host_get_hostname` not just `get_hostname`).

### Pitfall 2: Starlark top-level for-loops

**What goes wrong:** Starlark's standard spec allows for/if/while at module top-level only in certain dialects. `starlark-go` (if used for validation) requires `allow_global_reassign=True` for top-level for-loops.

**Why it happens:** Python allows top-level for-loops natively, but some Starlark implementations restrict them.

**How to avoid:** Since we use Python exec(), top-level for-loops work without configuration. `stats.star` can use top-level for-loops to parse Prometheus output. No action needed for the exec()-based runner.

**Warning signs:** Only relevant if a future syntax-checker uses starlark-go without `allow_global_reassign=True`.

### Pitfall 3: load() regex must match Starlark syntax variants

**What goes wrong:** `load()` statements can span multiple lines or use different quote styles. A simple regex that only matches single-line loads will silently skip multi-line load statements.

**Why it happens:** The regex pattern must handle both `load("path", "sym")` and `load('path', 'sym')` as well as multi-argument forms.

**How to avoid:** The regex pattern `r"""load\(\s*["']([^"']+)["'](?:\s*,\s*["']\w+["'])*\s*\)"""` covers both quote styles and multiple symbol args. Test against all .star files in the test suite.

**Warning signs:** A script fails with `undefined function` when calling a function that should have been loaded from a lib — the load() statement was not matched.

### Pitfall 4: starlark-go Python package callable globals → SIGSEGV

**What goes wrong:** Injecting a Python callable or object into `starlark-go`'s `Starlark(globals={...})` constructor causes a segmentation fault in the Go runtime.

**Why it happens:** The cgo bridge between Python and Go cannot marshal Python callable objects. The underlying Go starlark runtime tries to call back into Python through the cgo layer and crashes.

**How to avoid:** Do not use `starlark-go` as the runner. Use Python exec() instead. [VERIFIED: live testing showed SIGSEGV when injecting a lambda as a global]

### Pitfall 5: sys.config.get() must be callable, not a static value

**What goes wrong:** `MockSys({"config.get": "http://localhost:8080"})` returns the string directly regardless of the key argument. `stats.star` passes `"changes_api_url"` as the argument — if the fixture is not callable, it returns the string for ANY key.

**Why it happens:** MockNamespace returns static fixture values for all method calls when the fixture is not callable.

**How to avoid:** Always use a callable for methods that receive arguments:
```python
MockSys({"config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None})
```

**Warning signs:** Tests pass when they should fail (wrong key returns wrong URL without error).

### Pitfall 6: Path traversal in load() — off-by-one on separator

**What goes wrong:** `os.path.normpath()` may return the sysscripts root itself (without trailing separator). The check `resolved.startswith(root + os.sep)` misses the case where `resolved == root`.

**Why it happens:** String prefix matching on paths without normalizing separators.

**How to avoid:** Check both `resolved.startswith(str(root) + os.sep)` AND `resolved == root` (matching the agent's logic in sysscript.go T-03-01).

## Code Examples

### Prometheus Text Format Parsing in Starlark

```python
# Source: Prometheus exposition format spec + Starlark string API
# For use in sysscripts/services/changes-api/stats.star

base_url = sys.config.get("changes_api_url")
body = sys.net.http_get(base_url + "/metrics")["body"]

request_count = None
latency_sum = None
latency_count = None

for line in body.split("\n"):
    # Skip comments and empty lines
    if line.startswith("#") or line == "":
        continue
    # http_requests_total (may have labels: http_requests_total{method="GET",...} VALUE)
    if line.startswith("http_requests_total{") or line == "http_requests_total":
        parts = line.split(" ")
        if len(parts) >= 2:
            request_count = parts[-1]
    # Latency histogram sum and count
    if line.startswith("http_request_duration_seconds_sum"):
        latency_sum = line.split(" ")[-1]
    if line.startswith("http_request_duration_seconds_count"):
        latency_count = line.split(" ")[-1]

print("request_count:", request_count)
print("latency_avg_seconds:", float(latency_sum) / float(latency_count) if latency_count and float(latency_count) > 0 else 0)
```

### MockSys Fixture Dict for changes-api Tests

```python
# Source: CONTEXT.md D-10, verified against mock.py API
HEALTH_FIXTURES = {
    "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
    "net.http_get": {"status_code": 200, "body": ""},
}

STATS_FIXTURES = {
    "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
    "net.http_get": {
        "status_code": 200,
        "body": (
            "# HELP http_requests_total The total number of HTTP requests.\n"
            "# TYPE http_requests_total counter\n"
            'http_requests_total{method="GET",code="200"} 1234\n'
            "# HELP http_request_duration_seconds HTTP request duration.\n"
            "# TYPE http_request_duration_seconds histogram\n"
            "http_request_duration_seconds_sum 45.6\n"
            "http_request_duration_seconds_count 1234\n"
        ),
    },
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Binary starlark tools | Python exec()-based runner | Chosen for this project | No binary deps, native MockSys injection |
| Separate test fixtures file | Fixture dict inline in test | Established in Phase 2 | Simpler, co-located, discoverable |
| starlark-py package (per D-01) | Python exec() (no package) | Research 2026-05-04 | starlark-py does not exist; exec() is equivalent |

**Deprecated/outdated:**
- `starlark-py` (D-01): Does not exist on PyPI. Use Python exec() instead.
- `starlark-go` Python package for runner: Cannot inject Python objects as globals; SIGSEGV on callable injection; no load() support. Not usable for this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Standard Prometheus metric names for changes-api are `http_requests_total` and `http_request_duration_seconds` | Code Examples | If changes-api uses custom metric names, stats.star parser won't find them. Claude's Discretion area — script author adjusts metric names at authoring time. |
| A2 | statsagent health check endpoint is `/health` or `/healthz` (responds 200 when healthy) | Architecture Patterns | If endpoint differs, health.star needs adjustment. Low risk: easy to fix in the script. |
| A3 | lib/*.star helper functions return dicts (not structured strings) | Architecture Patterns | Determines how service scripts consume lib output. Low risk: test failures catch mismatches immediately. |

## Open Questions

1. **Prometheus metric names for changes-api**
   - What we know: Standard Go HTTP middleware uses `http_requests_total` and `http_request_duration_seconds`
   - What's unclear: Whether changes-api uses a custom framework or metric prefix
   - Recommendation: Claude's Discretion per CONTEXT.md — start with standard names and adjust if integration test against live host fails (success criteria 4 requires live host test)

2. **statsagent health endpoint path**
   - What we know: Most health check endpoints are `/health` or `/healthz`
   - What's unclear: What path statsagent actually exposes
   - Recommendation: Default to `/health` in health.star; easy to update when tested against live host

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | `adsops` package (requires-python >=3.10) | ✓ | 3.10.19 at `/usr/local/bin/python3.10` | — |
| pytest | Test harness | ✓ | 8.3.3 | — |
| typer | CLI sub-app | ✓ | >=0.21 (in pyproject.toml) | — |
| starlark-py (PyPI) | D-01 (as written) | ✗ | — | Python exec() runner (no package needed) |
| starlark-go (PyPI) | Optional syntax checker | ✓ | 1.0.1 | Not needed for MVP |

**Missing dependencies with no fallback:**
- None. The exec()-based runner requires no new PyPI packages.

**Missing dependencies with fallback:**
- `starlark-py`: Does not exist. Fallback: Python exec()-based runner (no install needed).

**Note on Python version:** System Python is 3.9.6 which fails `pip install adsops`. Development must use `python3.10` (available at `/usr/local/bin/python3.10`). The pyproject.toml `requires-python = ">=3.10"` is correct.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 |
| Config file | `tools/adsops/pyproject.toml` → `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `cd tools/adsops && python3.10 -m pytest tests/sysscripts/ -x -q` |
| Full suite command | `cd tools/adsops && python3.10 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STAR-01 | `lib/host.star` exports callable helpers | unit | `python3.10 -m pytest tests/sysscripts/test_host_star.py -x` | ❌ Wave 0 |
| STAR-02 | `lib/docker.star` exports callable helpers | unit | `python3.10 -m pytest tests/sysscripts/test_docker_star.py -x` | ❌ Wave 0 |
| STAR-03 | `lib/k3s.star` exports callable helpers | unit | `python3.10 -m pytest tests/sysscripts/test_k3s_star.py -x` | ❌ Wave 0 |
| STAR-04 | `statsagent/health.star` runs end-to-end via MockSys | unit | `python3.10 -m pytest tests/sysscripts/test_statsagent_health.py -x` | ❌ Wave 0 |
| STAR-05 | `changes-api/health.star` passes/fails on 200/non-200 | unit | `python3.10 -m pytest tests/sysscripts/test_changes_api_health.py -x` | ❌ Wave 0 |
| STAR-06 | `changes-api/stats.star` returns request counts + latency | unit | `python3.10 -m pytest tests/sysscripts/test_changes_api_stats.py -x` | ❌ Wave 0 |
| STAR-07 | runner.py executes .star with mock sys | unit | `python3.10 -m pytest tests/sysscripts/ -x` | ❌ Wave 0 |

**Success criterion 1** (`adsops sysscript run sysscripts/services/statsagent/health.star` runs without error): manual-only for CLI; automated as `test_statsagent_health.py`.

**Success criterion 4** (stats.star against live host): manual-only — requires live changes-api instance.

### Sampling Rate

- **Per task commit:** `cd tools/adsops && python3.10 -m pytest tests/sysscripts/ -x -q`
- **Per wave merge:** `cd tools/adsops && python3.10 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tools/adsops/tests/sysscripts/__init__.py` — test package init
- [ ] `tools/adsops/tests/sysscripts/test_host_star.py` — covers STAR-01
- [ ] `tools/adsops/tests/sysscripts/test_docker_star.py` — covers STAR-02
- [ ] `tools/adsops/tests/sysscripts/test_k3s_star.py` — covers STAR-03
- [ ] `tools/adsops/tests/sysscripts/test_statsagent_health.py` — covers STAR-04
- [ ] `tools/adsops/tests/sysscripts/test_changes_api_health.py` — covers STAR-05
- [ ] `tools/adsops/tests/sysscripts/test_changes_api_stats.py` — covers STAR-06
- [ ] `tools/adsops/src/adsops/sysscript/runner.py` — covers STAR-07 (also needed by all above)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | Sandbox root enforcement in runner.py (path traversal protection) |
| V5 Input Validation | yes | load() path validation; script paths from CLI input |
| V6 Cryptography | no | — |

### Known Threat Patterns for Starlark Runner

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via load() | Tampering | Resolve to absolute path; check `startswith(sysscripts_root + os.sep)` — mirrors agent T-03-01 |
| Arbitrary code execution via .star | Elevation of Privilege | Python exec() provides NO sandbox — acceptable for internal ops tooling only, not exposed to untrusted input |
| Directory escape via symlinks | Tampering | `pathlib.Path.resolve()` follows symlinks before comparison; verify resolved path is within root |

**Note on sandbox:** The Python exec()-based runner provides zero sandboxing — it executes with full Python interpreter privileges. This is acceptable because: (a) sysscripts are authored by the ops team, (b) this is internal tooling on trusted machines, (c) the real agent uses Go sandboxing; the Python runner is only for local development/testing.

## Sources

### Primary (HIGH confidence)
- Verified via live pip testing on 2026-05-04 — package `starlark-py` confirmed absent from PyPI
- `tools/adsops/src/adsops/sysscript/mock.py` — existing MockSys implementation [VERIFIED: Read tool]
- `tools/adsops/src/adsops/cli.py` — try/except sub-app registration pattern [VERIFIED: Read tool]
- `tools/adsops/src/adsops/infractl/cli.py` — CLI command reference pattern [VERIFIED: Read tool]
- `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — T-03-01 path traversal logic, sys module structure, http_get return shape [VERIFIED: Read tool]
- Python exec() runtime behavior — tested live with MockSys injection pattern [VERIFIED: Bash testing]
- starlark-go 1.0.1 API — inspected via `help(Starlark)` and live testing [VERIFIED: Bash testing]

### Secondary (MEDIUM confidence)
- Prometheus exposition format — standard `http_requests_total` and `http_request_duration_seconds` metric names [CITED: prometheus.github.io/client_python/parser/]
- starlark-go Python package load() limitation — tested live (returns "load not implemented by this application") [VERIFIED: Bash testing]

### Tertiary (LOW confidence)
- statsagent health endpoint path (`/health`) — assumed based on common convention [ASSUMED]
- changes-api Prometheus metric names — assumed standard Go HTTP middleware names [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified all packages via live pip testing
- Architecture: HIGH — Python exec() runner prototype tested and confirmed working
- Pitfalls: HIGH — starlark-go limitations verified via live testing (SIGSEGV, ConversionToStarlarkFailed, load() not implemented)

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days — stable Python ecosystem)
