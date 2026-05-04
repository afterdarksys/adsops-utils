# Phase 4: Sysscript Ecosystem - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A working Sysscript ecosystem: a shared Starlark helper library (`sysscripts/lib/`), per-service health and stats scripts (`sysscripts/services/`), an `adsops sysscript run` CLI command for local execution with MockSys, and per-script tests in `tools/adsops/tests/sysscripts/`.

Delivers:
- `sysscripts/lib/host.star`, `sysscripts/lib/docker.star`, `sysscripts/lib/k3s.star` — importable shared helpers
- `sysscripts/services/statsagent/health.star` — statsagent health check
- `sysscripts/services/changes-api/health.star` — changes-api HTTP health check
- `sysscripts/services/changes-api/stats.star` — changes-api request counts + latency from Prometheus
- `adsops sysscript run <script.star>` — local runner using Python exec()-based interpreter + empty MockSys
- Tests for each .star script in `tools/adsops/tests/sysscripts/`

Does NOT deliver: remote execution (the agent already handles that), inventory hierarchy (Phase 5), deployment artifacts (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Starlark Runner
- **D-01:** Use Python `exec()`-based runner as the local Starlark interpreter — pure Python, no binary dependencies. (`starlark-py` does not exist on PyPI; pure-Python `exec()` is equivalent in spirit and was verified 2026-05-04.)
- **D-02:** `sys` is injected as a **predefined global** before script evaluation — same pattern as the real agent. Script authors use `sys.net.http_get(...)` naturally without a `load()` call for it.
- **D-03:** Default local run uses an **empty MockSys** — any `sys.*` call raises `NotImplementedError` with a helpful message listing the missing fixture key. This makes the script's dependencies visible and ensures tests always provide explicit fixtures.
- **D-04:** `adsops sysscript run <script.star>` is the CLI surface. No `--fixture` flag for MVP; fixture data is only used in tests, not via the CLI.

### load() Path Resolution
- **D-05:** Service scripts use **relative paths** for `load()`: e.g., `load("../../lib/host.star", "host_info")`. Paths are relative to the script file's location. The runner resolves them at execution time.
- **D-06:** The **sandbox root is `sysscripts/`** — the runner rejects any `load()` path that resolves outside the `sysscripts/` directory tree. Consistent with the Thread.Load path traversal protection already in the agent (T-03-01).
- **D-07:** Runner auto-discovers the `sysscripts/` root as the nearest ancestor directory of the script being run that is named `sysscripts`. No explicit config needed.

### changes-api Scripts
- **D-08:** `changes-api/health.star` calls `sys.net.http_get(base_url + "/health")` (or `/healthz`) and checks for HTTP 200. A non-200 response signals unhealthy.
- **D-09:** `changes-api/stats.star` calls `sys.net.http_get(base_url + "/metrics")`, parses Prometheus text-format output, and extracts request count and latency histogram values.
- **D-10:** Both changes-api scripts read the base URL via `sys.config.get("changes_api_url")`. No hardcoded hostname. Tests provide this via MockSys fixture: `{"config.get": lambda key: "http://localhost:8080" if key == "changes_api_url" else None}`.

### Claude's Discretion
- Exact Prometheus metric names to parse in stats.star (standard http_requests_total and http_request_duration_seconds histogram patterns unless changes-api uses custom names)
- Starlark helper function signatures within lib/ files
- Whether lib/ helpers return dicts or structured strings
- Test fixture file format and location within `tests/sysscripts/`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing MockSys harness (Phase 2 output — reuse, don't replace)
- `tools/adsops/src/adsops/sysscript/mock.py` — MockSys and MockNamespace implementation; all 15 namespaces defined
- `tools/adsops/tests/test_mocksys.py` — MockSys usage patterns and fixture conventions

### Existing Python CLI structure (follow established patterns)
- `tools/adsops/src/adsops/cli.py` — main Typer app; sysscript sub-app must be registered here via the try/except import pattern
- `tools/adsops/src/adsops/infractl/cli.py` — reference for how sub-apps and commands are structured

### Agent sysscript engine (understand runtime parity)
- `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — Thread.Load path protection, sys global injection pattern, load() resolution logic in the real agent

### Requirements
- `.planning/REQUIREMENTS.md` §Sysscript Ecosystem — STAR-01 through STAR-07

### Python package config
- `tools/adsops/pyproject.toml` — no new dependency needed (exec()-based runner uses stdlib only)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `adsops.sysscript.mock.MockSys` — already built and tested; the runner uses this directly for local execution and tests use it with explicit fixture dicts
- `adsops.sysscript.mock.MockNamespace` — the per-namespace fixture handler; tests patch individual `namespace.method` keys
- Typer sub-app pattern — `infractl/cli.py` shows the exact pattern for adding a new `sysscript` sub-app with a `run` command

### Established Patterns
- **Fixture-dict MockSys** — tests pass `{"net.http_get": "response", "config.get": lambda k: ...}` to MockSys constructor. All sysscript tests must follow this pattern.
- **try/except import registration** — `cli.py` registers sub-apps with try/except so missing modules degrade gracefully; sysscript CLI must follow this.
- **Relative load() in Starlark** — the agent's Thread.Load uses `filepath.Clean` + `HasPrefix` against a base path; the Python runner replicates this logic.

### Integration Points
- `tools/adsops/src/adsops/sysscript/` — new `runner.py` module goes here alongside `mock.py`
- `sysscripts/` — new top-level directory in the repo root; lib/ and services/ live here
- `tools/adsops/tests/sysscripts/` — new test subdirectory; one test file per .star script

</code_context>

<specifics>
## Specific Ideas

- Python exec()-based runner is the interpreter — no new PyPI dependency needed (starlark-py does not exist on PyPI)
- `adsops sysscript run` with empty MockSys is a development/introspection tool — it shows you which `sys.*` calls the script needs, not a live runner
- changes-api Prometheus metrics: use standard `http_requests_total` and `http_request_duration_seconds` bucket patterns; if the actual metrics differ, the script author adjusts the parser
- The sandbox root discovery (`nearest sysscripts/ ancestor`) means you can run from any directory and it still works

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-Sysscript Ecosystem*
*Context gathered: 2026-05-04*
