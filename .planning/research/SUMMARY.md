# Project Research Summary

**Project:** adsops-utils toolkit overhaul
**Domain:** Infrastructure ops tooling — Go CLI suite + Python mirror + proto contracts + Starlark scripting agent
**Researched:** 2026-05-03
**Confidence:** HIGH (stack, packaging, architecture); MEDIUM (Starlark Python mock pattern)

## Executive Summary

This overhaul adds three distinct capabilities to adsops-utils: a shared proto contract layer (buf + google-protobuf) to unify Go and Python data types, a first-class Python CLI package (Typer + paramiko) that mirrors the existing Go toolchain, and a Starlark scripting engine (systemapi-agent) that executes host management scripts using a `sys.*` namespace backed by the existing Docker socket client from statsagent. The recommended approach for each layer is well-documented and follows patterns already proven in the codebase — buf for proto generation, setuptools src-layout for the Python package, and go.starlark.net with a `Thread.Load` callback for the script engine.

The most critical cross-cutting constraint is phase ordering: proto schemas must exist and be generated before the Python package can import them, and `Thread.Load` must be wired into systemapi-agent before any `.star` script using `load()` will execute. The inventory and deployment phases are largely additive and self-contained, but the infractl scan writeback to inventory depends on the `metadata` column being `jsonb` (not `json`), which may require a one-time non-destructive migration before that work begins.

The main risk area is the Python Starlark test harness: `python-starlark-go` requires Go at build time (CGo), which is acceptable for an internal tool but should be called out explicitly in the phase plan. betterproto must be avoided entirely — it is in active redesign and unsuitable for stable infrastructure tooling. The SQLite dependency in hostctl requires `CGO_ENABLED=1` in its Dockerfile; migration to `modernc.org/sqlite` would eliminate this constraint and is worth evaluating before the deployment phase.

## Key Findings

### Recommended Stack

The toolchain is buf for proto generation (no protoc required, BSR remote plugins, built-in lint and breaking-change detection), google-protobuf official runtime for Python (betterproto is explicitly ruled out), Typer 0.12+ for the Python CLI (maps `add_typer()` directly onto Cobra's `AddCommand()` pattern), paramiko for SSH execution in Python (asyncssh as opt-in upgrade for fan-out commands), and go.starlark.net for the Starlark interpreter in systemapi-agent.

**Core technologies:**
- `buf` (BSR remote plugins): proto generation — deterministic, no local plugin installs, enforces naming and breaking-change rules
- `google-protobuf >= 5.26` + `mypy-protobuf`: Python proto runtime — official, stable, IDE-friendly via `.pyi` stubs; betterproto/betterproto2 explicitly ruled out
- `Typer[all] >= 0.12` + `rich`: Python CLI framework — type-hint-driven, maps cleanly to Go/Cobra command tree via `add_typer()`
- `paramiko >= 3.4`: Python SSH execution — pure Python, respects `~/.ssh/config`, sufficient for synchronous CLI ops; asyncssh for fan-out if needed later
- `go.starlark.net` + `starlarkstruct.Module`: Starlark engine + `sys.*` namespace — official Go implementation, immutable attribute-access module pattern
- Raw HTTP over `/var/run/docker.sock` (copy statsagent pattern): Docker client in agent — zero new dependencies, already proven in codebase
- `setuptools` + `src/` layout + `[project.scripts]`: Python packaging — standard, editable-install friendly, `adsops` entry point in venv `bin/`

### Expected Features

This is an internal ops tooling project. The "features" are capabilities surfaced to the ops team.

**Must have (table stakes):**
- Proto-defined data types shared between Go tools and Python tools — consistency across toolchain
- `adsops` CLI with `hosts`, `infra`, `stats` subcommands mirroring Go toolchain
- SSH remote execution from Python (paramiko) — parity with Go infractl
- Starlark `sys.containers.list()` / `sys.containers.stats()` backed by Docker socket
- `load()` support in sysscripts via `Thread.Load` + `ScriptLoader` with caching and cycle detection
- Hierarchical inventory (host → container/pod) stored in existing `metadata` jsonb column
- `hostctl list --children` tree view without breaking existing tabular output

**Should have (useful additions):**
- `sys.has(feature_name)` builtin for capability probing in scripts
- `@`-prefix virtual module loader (tamper-proof stdlib from `embed.FS`)
- asyncssh fan-out mode for `adsops infra` commands targeting multiple hosts
- `infractl scan` writeback to populate `children` in inventory metadata
- statsagent and systemapi-agent k3s DaemonSet manifests in `deployments/kubernetes/`
- `docker compose --profile tools` integration for hostctl and statsagent in local dev

**Defer (v2+):**
- gRPC service definitions (buf grpc Python plugin has a known incompatibility; v1 uses message types only)
- Separate versioned `gen/go/` Go module (use `replace` directive during active development; promote before CI/CD)
- BSR push of proto module (only needed if external consumers exist)
- asyncssh fan-out as default (start with paramiko; switch only if `infra deploy --all` latency is observed)

### Architecture Approach

The architecture is a layered monorepo: proto schemas in `proto/` generate into `gen/go/` and `gen/python/`, consumed upstream by both the Go tools and the Python package. systemapi-agent imports Go proto bindings and runs Starlark scripts via a `ScriptLoader` that resolves `load()` paths from a configured `BaseDir`. The Python package uses a strict `api.py` / `commands.py` split (mirroring Go's `internal/` vs `cmd/` separation) with a `SysInterface` Protocol that both `MockSys` and `LiveSys` satisfy, enabling unit tests without subprocess or Starlark execution overhead.

**Major components:**
1. `proto/` + `buf.gen.yaml` — schema source of truth; generates `gen/go/` and `gen/python/` via `make proto`
2. `gen/python/` as `adsops-proto` local package — installed with `pip install -e gen/python/` in dev; consumed by `tools/adsops/`
3. `tools/adsops/` (Python package) — `src/adsops/` with `cli.py` wiring, per-domain `api.py` + `commands.py`, `sys/` Protocol + mock
4. `systemapi-agent` — Go binary with `ScriptLoader` + `Thread.Load` callback, `buildSysModule(AgentConfig)` gating capabilities at construction, Docker client reused from statsagent
5. `tools/hostctl/` + `tools/infractl/` (existing, extended) — `ListOptions.ShowChildren`, `printResourceTree`, `patchMetadata()` writeback
6. `deployments/kubernetes/` — DaemonSet manifests for statsagent (read-only) and systemapi-agent (privileged, `hostNetwork: true`)

### Critical Pitfalls

1. **betterproto / betterproto2 in Python** — Do not use either. betterproto is unmaintained; betterproto2 is mid-redesign with breaking API changes as of 2025. Use `google-protobuf` + `mypy-protobuf`. Hard constraint.

2. **`Thread.Load` not set = all `load()` calls fail silently at runtime** — go.starlark.net does not enable `load()` by default. If `thread.Load` is nil, any `.star` script using `load("lib/health.star", ...)` raises a runtime error with no indication that the host program is responsible. Wire `ScriptLoader.Load` onto every `Thread`, including threads created for transitive loads.

3. **`mattn/go-sqlite3` requires `CGO_ENABLED=1`** — hostctl's Dockerfile must use Alpine builder with `gcc musl-dev sqlite-dev` and `-linkmode external -extldflags '-static'`. Skipping CGO produces a link error. Evaluate migrating to `modernc.org/sqlite` (pure Go) before the deployment phase.

4. **`metadata` column must be `jsonb` not `json`** — the `->` and `@>` JSON path operators require `jsonb`. If the column is `json`, run `ALTER COLUMN metadata TYPE jsonb USING metadata::jsonb` before implementing infractl scan writeback. Non-destructive but must precede that work.

5. **Typer >= 0.14.0 sub-app name inference removed** — always pass `name=` explicitly to `app.add_typer()`. Omitting it silently produces broken CLI output with no error.

6. **`paths=source_relative` required for Go proto generation** — without this, protoc-gen-go generates files in unexpected nested paths. Always set in `buf.gen.yaml`.

7. **Commit `gen/` directory** — both systemapi-agent (Go) and tools/adsops (Python) must be able to import without buf installed. Add `make proto` as the regeneration entry point.

## Implications for Roadmap

The 6-phase plan in the project context is well-ordered. The annotations below confirm ordering rationale and add specific constraints each phase must address.

### Phase 1: Proto Toolchain

**Rationale:** Everything downstream (Python package, agent, inventory JSON export) depends on generated types. This must land first with committed `gen/` output so other phases can proceed without buf installed.
**Delivers:** `proto/` directory with versioned schemas, `buf.gen.yaml`, `gen/go/`, `gen/python/`, `make proto` / `make proto-lint` / `make proto-breaking` targets, `gen/python/pyproject.toml` (adsops-proto local package)
**Key decisions to lock in:** domain split (`telemetry/v1`, `host/v1`, `container/v1`), managed mode with `go_package_prefix`, google-protobuf runtime (not betterproto)
**Avoids:** betterproto churn; `go_package` options polluting proto files; uncommitted gen/ causing downstream import failures

### Phase 2: Python Package (tools/adsops)

**Rationale:** Depends on Phase 1 (needs `gen/python/` for proto imports). Establishes the Python CLI structure that all subsequent Python work builds on.
**Delivers:** `tools/adsops/` with `pyproject.toml`, `src/` layout, `adsops` entry point, `hosts/`, `infra/`, `stats/` sub-apps wired via Typer, `sys/` Protocol + MockSys, paramiko SSH execution
**Key decisions to lock in:** `src/` layout with `where = ["src"]` discovery, `name=` explicit on every `add_typer()` call, `api.py` / `commands.py` split as enforced convention, `SysInterface` Protocol (not ABC)
**Avoids:** Typer >= 0.14 name inference regression; flat module layout that makes api.py untestable without CLI invocation

### Phase 3: systemapi-agent (Starlark engine)

**Rationale:** Depends on Phase 1 (imports Go proto bindings via `replace` directive or `gen/go/` module). Docker client copied from statsagent; `ScriptLoader` is self-contained.
**Delivers:** `ScriptLoader` with `Thread.Load`, `buildSysModule(AgentConfig)` with capability gating, `sys.containers.list/stats` builtins, agent binary with configurable `SysscriptDir`
**Key decisions to lock in:** capability gating at construction (not per-call), `starlark.None` (not error) when Docker unavailable, `ScriptLoader.predeclared` passed through to transitive `load()` threads, `replace` directive for gen/go during development
**Avoids:** `Thread.Load = nil` runtime failures; importing moby/docker SDK (100+ deps); per-call permission checks that require runtime state synchronization

### Phase 4: sysscripts Library

**Rationale:** Depends on Phase 3 (agent must be running to validate scripts). The `@`-prefix virtual module loader is optional for v1 but the decision should be made before the library grows.
**Delivers:** `sysscripts/lib/health.star`, `sysscripts/lib/fmt.star`, service scripts (nginx, postgres), `BaseDir`-relative `load()` resolution
**Key decisions to lock in:** relative path convention vs `@`-prefix stdlib, whether built-in libs ship via `embed.FS` or on-disk
**Avoids:** absolute paths in `load()` calls that break across deployment environments

### Phase 5: Inventory Hierarchy

**Rationale:** Self-contained hostctl/infractl change. Depends on confirming `metadata` column type before writing any JSON path queries.
**Delivers:** `ListOptions.ShowChildren`, `printResourceTree` in output.go, `patchMetadata()` in infractl, infractl scan writeback populating `children` array, `_children_version` + `_last_scan` metadata keys
**Pre-condition:** Confirm `metadata` column is `jsonb`; run `ALTER COLUMN` migration if not.
**Key decisions to lock in:** `patchMetadata` as a direct `UPDATE ... SET metadata` (not routed through `updateResource`), replace-on-scan (not merge) for stale child cleanup
**Avoids:** `updateResource` clobbering children; `json` column type blocking JSON path queries

### Phase 6: Deployment Artifacts

**Rationale:** Depends on all prior phases having stable binaries to containerize. CGO decision for hostctl must be resolved before writing its Dockerfile.
**Delivers:** `tools/hostctl/Dockerfile` (CGO or pure-Go based on sqlite driver), `tools/infractl/Dockerfile` (CGO_ENABLED=0, optional distroless runtime), `deployments/kubernetes/statsagent-daemonset.yaml`, `deployments/kubernetes/systemapi-agent-daemonset.yaml`, docker-compose profile additions for `tools` and `monitoring`
**Pre-condition:** Check `tools/hostctl/go.mod` for `mattn/go-sqlite3` vs `modernc.org/sqlite`. If mattn, use CGO Dockerfile pattern. If modernc, use CGO_ENABLED=0 (simpler, matches statsagent pattern).
**Avoids:** CGO_ENABLED=0 build failure for hostctl with mattn sqlite; `hostNetwork: true` missing `dnsPolicy: ClusterFirstWithHostNet`; statsagent getting privileged access it does not need

### Phase Ordering Rationale

- Protos first is non-negotiable: both `gen/go/` and `gen/python/` are imported by Phase 2 and Phase 3 respectively, and committing generated output unblocks all downstream phases from running without buf.
- Python package before sysscripts: the `MockSys` / `SysInterface` pattern established in Phase 2 is the test harness for validating sysscript behavior from Python; having it early reduces debug friction in Phase 4.
- systemapi-agent before sysscript library: `load()` cannot be validated until the agent's `ScriptLoader` is wired. Writing lib scripts against a non-functional loader wastes iteration time.
- Inventory before deployment: the infractl scan writeback (Phase 5) needs to be validated against a live inventory DB before baking infractl into a container image (Phase 6).

### Research Flags

Phases with complete research, no further research needed:
- **Phase 1 (Proto Toolchain):** Fully specified. buf docs HIGH confidence; implementation is mechanical.
- **Phase 2 (Python Package):** Fully specified. All decisions locked (Typer, paramiko, src layout, Protocol pattern).
- **Phase 5 (Inventory):** Additive to existing code. Only pre-condition is confirming jsonb column type.
- **Phase 6 (Deployment):** Patterns documented. Only conditional is hostctl sqlite driver choice.

Phases that may benefit from a targeted spike before planning:
- **Phase 3 (systemapi-agent):** The `replace` directive vs separate `gen/go/` Go module decision needs to be made explicit before agent CI/CD is wired.
- **Phase 4 (sysscripts):** The `@`-prefix virtual module pattern is clean but untested in this codebase. A small spike to validate `embed.FS` + `ScriptLoader` together is worth budgeting.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Proto toolchain (buf, gen layout, managed mode) | HIGH | buf docs + BSR remote plugin docs verified |
| Python runtime choice (google-protobuf over betterproto) | HIGH | betterproto instability confirmed via multiple sources |
| Python packaging (Typer, setuptools src layout) | HIGH | Context7 Typer 0.21.1 + Python Packaging User Guide |
| paramiko SSH execution | HIGH | Context7 paramiko docs, matches existing Go SSH pattern |
| go.starlark.net Thread.Load pattern | HIGH | Context7 starlark-go, canonical loader pattern confirmed |
| Docker socket client reuse from statsagent | HIGH | Verified against tools/statsagent/collectors/docker.go in repo |
| Starlark Python test harness (python-starlark-go) | MEDIUM | PyPI confirmed, CGo dep acceptable; predeclared injection pattern standard but not validated against this project's sys.* shape |
| Inventory metadata jsonb hierarchy | HIGH | Postgres jsonb operators documented; `_children_version` versioning is conventional |
| hostctl CGO/sqlite Dockerfile | HIGH | Alpine musl static linking pattern is well-established; conditioned on sqlite driver in use |

**Overall confidence:** HIGH

### Gaps to Address

- **`metadata` column type in production DB:** Must be confirmed (`json` vs `jsonb`) before Phase 5 work begins. Query: `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'inventory_resources' AND column_name = 'metadata'`.
- **hostctl sqlite driver:** Check `tools/hostctl/go.mod` for `mattn/go-sqlite3` vs `modernc.org/sqlite` before writing the Phase 6 Dockerfile. Determines whether CGO_ENABLED=1 is required in CI/CD.
- **`gen/go/` module strategy at Phase 3:** The roadmap should explicitly note when to promote from `replace` directive to a separate `gen/go/go.mod` (before systemapi-agent CI/CD is wired, not after).
- **python-starlark-go CGo in CI:** If the Python test suite runs in CI without a Go toolchain, `starlark-go` (PyPI) will fail to install. The roadmap should clarify whether CI needs Go for Python tests, or whether sysscript integration tests are separated from the unit test suite.

## Sources

### Primary (HIGH confidence)

- buf CLI GitHub + buf.build docs (generate, buf-gen-yaml v2, BSR Python SDKs) — proto toolchain decisions
- Context7 /google/starlark-go — Thread.Load pattern, NewBuiltin, starlarkstruct.Module
- Context7 /fastapi/typer (v0.21.1) — add_typer name= requirement, subcommand wiring
- Context7 /paramiko/paramiko — exec_command pattern, load_system_host_keys
- Python Packaging User Guide + PEP 660 — pyproject.toml src layout, editable installs
- mypy-protobuf PyPI + nipunn1313/mypy-protobuf GitHub — .pyi stub generation
- tools/statsagent/collectors/docker.go (this repo) — Docker socket client pattern, CPU% delta math
- Docker Engine API docs — /containers/json, /stats?stream=false behavior
- Go Modules Reference (go.dev) — replace directive constraints, multi-module monorepo
- Postgres jsonb docs — @>, ->, jsonb_array_length operators

### Secondary (MEDIUM confidence)

- python-starlark-go PyPI / starlark-go docs — predeclared injection API for test harness
- betterproto2 GitHub — instability assessment (active major redesign confirmed)
- buf issue #1344 — grpc_tools Python incompatibility (relevant for v2 if gRPC added)

### Tertiary (inference from existing codebase)

- tools/hostctl/go.mod — sqlite driver assumption (needs verification before Phase 6)
- deployments/docker/docker-compose.yml — existing service names and env var conventions used as basis for compose extension

---
*Research completed: 2026-05-03*
*Ready for roadmap: yes*
