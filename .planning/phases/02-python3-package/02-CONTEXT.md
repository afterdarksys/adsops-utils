# Phase 2: Python3 Package - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A pip-installable `tools/adsops/` Python package (`adsops` CLI) that gives Python parity to Go hostctl, infractl, and statsagent — plus a MockSys test harness for running `.star` Sysscripts locally without a live agent.

Delivers: `adsops hostctl list/add/update/import-ssh-config`, `adsops infractl docker ls/start/stop/restart/logs/exec` and `adsops infractl k3s nodes/pods/logs/apply`, `adsops stats once`, and `adsops.sysscript.mock` (MockSys).

Does NOT deliver: actual sysscript execution, systemapi-agent integration, or inventory hierarchy (those are Phases 3–5).

</domain>

<decisions>
## Implementation Decisions

### Database (hostctl module)
- **D-01:** Use **SQLAlchemy ORM** as the PostgreSQL client (not psycopg2 directly).
- **D-02:** Read the same env vars as Go hostctl: `INVENTORY_DB_HOST`, `INVENTORY_DB_PORT`, `INVENTORY_DB_NAME`, `INVENTORY_DB_USER`, `INVENTORY_DB_PASSWORD`. No new Python-specific vars.
- **D-03:** SQLAlchemy models must mirror the Go `Resource` struct fields. Use `JSONB`/`dict` for `metadata`, `ARRAY` for `owners`/`mailgroups`, nullable columns for `region`, `external_id`, `external_url`, `average_daily_cost`, `average_monthly_cost`.

### SSH (infractl module)
- **D-04:** Use **asyncssh** (not paramiko) for SSH execution. This supersedes the `paramiko` mention in REQUIREMENTS.md — asyncssh is the chosen library.
- **D-05:** Authentication via **SSH agent only**. No key file resolution. asyncssh connects to the running ssh-agent socket.
- **D-06:** CLI entry points call `asyncio.run(async_fn())` — each Typer command is sync but wraps an async core. No sync wrapper layer.
- **D-07:** Support **multi-host parallel execution** via `asyncio.gather()`. Commands that accept a `<host>` argument can accept multiple hosts. Output is prefixed by hostname.

### MockSys (sysscript test harness)
- **D-08:** MockSys uses **configurable fixture data** — tests pass a dict of canned responses per namespace/call. MockSys returns fixture data when called. Deterministic, no real-agent dependency.
- **D-09:** MockSys covers **all namespaces from sysscript.go**: `sys.containers`, `sys.k3s`, `sys.exec`, `sys.fs`, `sys.net`, `sys.config`, `sys.yaml`, `sys.alerts`, `sys.security`, `sys.events`, `sys.packages`.
- **D-10:** MockSys is exposed as `adsops.sysscript.mock.MockSys`. Test scripts import it and pass it as the `sys` global when executing `.star` content via `starlark-go` Python bindings or via string evaluation.

### Proto integration (all modules)
- **D-11:** **All modules** use proto types as their internal data representation — not plain dicts. `adsops.hostctl` uses `HostRecord`, `adsops.infractl` uses `ContainerStats`/`K3sStats`, `adsops.stats` uses `StatsSnapshot`/`TelemetryPayload`.
- **D-12:** Import proto bindings from `gen/python/adsops/v1/` (committed in Phase 1). The `adsops-proto` package (`gen/python/pyproject.toml`) is a declared dependency of `tools/adsops/`.
- **D-13:** CLI output defaults to human-readable text. `--json` flag outputs proto JSON (via `MessageToJson` from `google.protobuf.json_format`). `--proto` flag outputs binary proto (for piping to other tools).

### Claude's Discretion
- Exact SQLAlchemy model class names and relationship mappings
- Typer command group hierarchy (nested app structure)
- Error handling and exit codes
- Logging verbosity levels
- asyncssh connection pooling / reuse within a single CLI invocation

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Go source — parity reference
- `tools/hostctl/types.go` — Resource struct (SQLAlchemy model must mirror this)
- `tools/hostctl/database.go` — PostgreSQL connection pattern and env vars
- `tools/hostctl/commands.go` — CLI command surface to replicate in Python
- `tools/infractl/cmd/docker.go` — Docker subcommands over SSH to replicate
- `tools/infractl/cmd/k3s.go` — k3s subcommands over SSH to replicate
- `tools/statsagent/collectors/docker.go` — DockerStats/ContainerStats struct (maps to proto)
- `tools/statsagent/collectors/k3s.go` — K3sStats struct (maps to proto)

### Proto bindings (Phase 1 output)
- `gen/python/adsops/v1/host_pb2.py` — HostRecord Python binding
- `gen/python/adsops/v1/container_pb2.py` — ContainerStats Python binding
- `gen/python/adsops/v1/k3s_pb2.py` — K3sStats Python binding
- `gen/python/adsops/v1/stats_pb2.py` — StatsSnapshot Python binding
- `gen/python/adsops/v1/telemetry_pb2.py` — TelemetryPayload Python binding
- `gen/python/pyproject.toml` — adsops-proto package (declare as dependency)

### Sysscript reference (for MockSys)
- `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — SysscriptEngine, all sys.* namespace implementations. MockSys must expose identical call signatures.

### Requirements
- `.planning/REQUIREMENTS.md` §Python3 Package — PY-01 through PY-07

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/infractl/ssh/config.go` — SSH config parser (ParseConfig, LookupHost). Python package should do the same from `~/.ssh/config` to resolve hostnames.
- `scripts/aftercloud/adsops_config.py` — Existing Python config loading pattern. Can inform env var resolution approach.

### Established Patterns
- Go hostctl uses PostgreSQL (lib/pq) NOT SQLite — Python must connect to the same PostgreSQL DB, not a local file.
- Go infractl runs SSH commands via `golang.org/x/crypto/ssh` — asyncssh is the Python equivalent.
- All Go tools read config from env vars with `os.Getenv` / `getEnvOrDefault` — Python should follow the same pattern.

### Integration Points
- `gen/python/` (Phase 1 output) — must be installed as `adsops-proto` dep before `tools/adsops/` package installs
- `~/.ssh/config` — source of truth for host resolution (same as Go infractl)
- PostgreSQL inventory DB — shared with Go hostctl, same schema

</code_context>

<specifics>
## Specific Ideas

- asyncssh chosen specifically because it makes multi-host parallel execution (`asyncio.gather()`) natural — this is a key differentiator over Go infractl which runs serially.
- All modules produce proto-typed output; CLI formats it for humans by default, with `--json` and `--proto` flags for machine consumption.
- MockSys covers all 11 sys namespaces from sysscript.go so any `.star` script can be tested locally regardless of which sys.* calls it uses.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-python3-package*
*Context gathered: 2026-05-04*
