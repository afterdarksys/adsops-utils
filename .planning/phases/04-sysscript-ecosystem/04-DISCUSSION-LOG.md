# Phase 4: Sysscript Ecosystem - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 4-Sysscript Ecosystem
**Areas discussed:** Starlark runner, changes-api endpoints, load() path resolution

---

## Starlark Runner

### Q1: How should `adsops sysscript run` execute .star files locally?

| Option | Description | Selected |
|--------|-------------|----------|
| starlark-py (PyPI) | Pure Python Starlark interpreter, no binary deps, pip install | ✓ |
| Subprocess go binary | Shell out to compiled agent binary — requires binary on PATH | |
| larky / other | Java-based or other interpreter | |

**User's choice:** starlark-py (Recommended)
**Notes:** Natural fit for a Python package; no OS coupling.

---

### Q2: How should MockSys be injected into the script's execution environment?

| Option | Description | Selected |
|--------|-------------|----------|
| Predefined global | Runner pre-defines `sys` as a global before evaluating the script | ✓ |
| load() from harness module | Script explicitly `load()`s mock sys | |
| CLI arg / env var | `--sys-fixture path/to/fixtures.json` flag | |

**User's choice:** Predefined global (Recommended)
**Notes:** Matches how the real agent injects `sys` — script authors see identical usage in local and remote contexts.

---

### Q3: What fixture data does the script get by default when running locally?

| Option | Description | Selected |
|--------|-------------|----------|
| Empty MockSys — errors on any sys call | NotImplementedError shows what fixtures are needed | ✓ |
| Passthrough to real sys | Actually calls Docker/k3s/etc. | |
| Auto-generated stubs | Introspects script and returns zero values | |

**User's choice:** Empty MockSys (Recommended)
**Notes:** Makes the script's sys dependencies explicit; tests always provide fixtures.

---

## changes-api Endpoints

### Q1: What does the health endpoint look like?

| Option | Description | Selected |
|--------|-------------|----------|
| HTTP /health or /healthz | Standard health endpoint, 200 = healthy | ✓ |
| No dedicated health — check a data endpoint | Call a real API route instead | |
| Let me describe it | Custom endpoint | |

**User's choice:** HTTP /health or /healthz

---

### Q2: Where do request counts and latency come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Prometheus /metrics endpoint | Parse Prometheus text format for request count + latency histograms | ✓ |
| Custom JSON /stats or /api/stats | JSON endpoint with request_count, avg_latency_ms fields | |
| Let me describe it | Custom endpoint | |

**User's choice:** Prometheus /metrics endpoint

---

### Q3: What's the default base URL for changes-api in the scripts?

| Option | Description | Selected |
|--------|-------------|----------|
| sys.config.get("changes_api_url") | Read URL from sysscript config namespace — no hardcoding | ✓ |
| Hardcoded internal hostname | e.g., http://changes-api.internal | |
| Script argument / parameter | Passed via CLI or test fixture | |

**User's choice:** sys.config.get("changes_api_url") (Recommended)

---

## load() Path Resolution

### Q1: What load() path convention should service scripts use?

| Option | Description | Selected |
|--------|-------------|----------|
| Relative path | `load("../../lib/host.star", "host_info")` — relative to script location | ✓ |
| Repo-root anchor // | `load("//sysscripts/lib/host.star", ...)` — Bazel-style absolute | |
| Bare name | `load("host", ...)` — runner searches configured lib path | |

**User's choice:** Relative path (Recommended)
**Notes:** Simple, no magic. Consistent with standard file resolution.

---

### Q2: What happens when a load() path resolves outside sysscripts/?

| Option | Description | Selected |
|--------|-------------|----------|
| Raise an error | Reject path traversal outside sysscripts/ — consistent with agent | ✓ |
| Allow it silently | Any file on disk can be load()ed | |

**User's choice:** Raise an error (Recommended)
**Notes:** Security-first; mirrors Thread.Load protection in the agent.

---

### Q3: What is the load() sandbox root?

| Option | Description | Selected |
|--------|-------------|----------|
| sysscripts/ dir | Nearest sysscripts/ ancestor of the script; auto-discovered | ✓ |
| Repo root | Full adsops-utils repo root | |
| Script's own directory | Only files relative to the script itself | |

**User's choice:** sysscripts/ dir (Recommended)
**Notes:** Tight scope; auto-discovery means no explicit config needed.

---

## Claude's Discretion

- Exact Prometheus metric names in stats.star (use standard http_requests_total / http_request_duration_seconds)
- Starlark helper function signatures in lib/ files
- Whether lib/ helpers return dicts or structured strings
- Test fixture file format and location within tests/sysscripts/

## Deferred Ideas

None — discussion stayed within phase scope.
