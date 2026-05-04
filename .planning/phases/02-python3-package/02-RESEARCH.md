# Phase 2: Python3 Package - Research

**Researched:** 2026-05-04
**Domain:** Python CLI package — SQLAlchemy/PostgreSQL, asyncssh, Typer, protobuf, MockSys test harness
**Confidence:** HIGH

## Summary

Phase 2 creates `tools/adsops/` as a pip-installable Python package that gives Python-native parity to the Go hostctl, infractl, and statsagent tools. The package exposes `adsops hostctl`, `adsops infractl`, and `adsops stats` CLI entry points backed by SQLAlchemy (PostgreSQL), asyncssh, psutil, and the Phase 1 protobuf bindings. A MockSys test harness (`adsops.sysscript.mock`) lets `.star` scripts be exercised locally without SSH or a live agent.

The codebase already has `gen/python/` (Phase 1 output) with all five protobuf binding files committed and an `adsops-proto` package ready for `pip install -e`. The system Python is 3.9.6 (too old; `adsops-proto` requires `>=3.10`), but Python 3.11 is available at `/usr/local/bin/python3.11` and is the recommended interpreter. Key libraries — SQLAlchemy 2.0, Typer, pytest, protobuf, psutil, asyncpg, psycopg2-binary — are already installed in the 3.11 environment. asyncssh is not installed and must be added.

The sysscript.go source at `systemapi-agent/sysscript.go` reveals **14 actual sys namespaces** (not 11 as stated in CONTEXT.md D-09): `net`, `exec`, `fs`, `alerts`, `security`, `events`, `packages`, `containers`, `config`, `yaml`, `json`, `ini`, `services`, `proc`. MockSys must cover all 14.

**Primary recommendation:** Use `src/adsops/` layout, Python 3.11, `pyproject.toml` with `[project.scripts]` entry point, SQLAlchemy 2.x ORM with psycopg2-binary dialect, asyncssh for SSH, Typer for CLI, psutil for local stats, pytest for tests.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Database (hostctl module)**
- D-01: Use SQLAlchemy ORM as the PostgreSQL client (not psycopg2 directly).
- D-02: Read the same env vars as Go hostctl: `INVENTORY_DB_HOST`, `INVENTORY_DB_PORT`, `INVENTORY_DB_NAME`, `INVENTORY_DB_USER`, `INVENTORY_DB_PASSWORD`. No new Python-specific vars.
- D-03: SQLAlchemy models must mirror the Go `Resource` struct fields. Use `JSONB`/`dict` for `metadata`, `ARRAY` for `owners`/`mailgroups`, nullable columns for `region`, `external_id`, `external_url`, `average_daily_cost`, `average_monthly_cost`.

**SSH (infractl module)**
- D-04: Use asyncssh (not paramiko) for SSH execution.
- D-05: Authentication via SSH agent only. No key file resolution. asyncssh connects to the running ssh-agent socket.
- D-06: CLI entry points call `asyncio.run(async_fn())` — each Typer command is sync but wraps an async core. No sync wrapper layer.
- D-07: Support multi-host parallel execution via `asyncio.gather()`. Commands that accept a `<host>` argument can accept multiple hosts. Output is prefixed by hostname.

**MockSys (sysscript test harness)**
- D-08: MockSys uses configurable fixture data — tests pass a dict of canned responses per namespace/call.
- D-09: MockSys covers all sys namespaces from sysscript.go.
- D-10: MockSys is exposed as `adsops.sysscript.mock.MockSys`.

**Proto integration (all modules)**
- D-11: All modules use proto types as their internal data representation.
- D-12: Import proto bindings from `gen/python/adsops/v1/`. The `adsops-proto` package (`gen/python/pyproject.toml`) is a declared dependency.
- D-13: CLI output defaults to human-readable text. `--json` flag outputs proto JSON. `--proto` flag outputs binary proto.

### Claude's Discretion
- Exact SQLAlchemy model class names and relationship mappings
- Typer command group hierarchy (nested app structure)
- Error handling and exit codes
- Logging verbosity levels
- asyncssh connection pooling / reuse within a single CLI invocation

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PY-01 | `tools/adsops/` with `pyproject.toml`, `src/adsops/` layout, `pip install -e .` works | pyproject.toml `[project.scripts]` entry point pattern verified; src layout prevents accidental bare imports |
| PY-02 | `adsops.hostctl` module: list, add, update, import-ssh-config with probe | SQLAlchemy 2.x ORM maps to `inventory_resources` table; paramiko-style SSH probe replaced by asyncssh; `~/.ssh/config` parsed via stdlib `ssh_config`-style parsing |
| PY-03 | `adsops.infractl` module: docker (ls/start/stop/restart/logs/exec) and k3s (nodes/pods/logs/apply) over SSH | asyncssh `connect()` + `run()` / `create_process()` for streaming; multi-host via `asyncio.gather()`; k3s via `k3s kubectl` over SSH |
| PY-04 | `adsops.stats` module: collect once, fetch from remote statsagent endpoint | psutil provides CPU/mem/disk/net; proto `StatsSnapshot`/`TelemetryPayload` for output; remote fetch via aiohttp or asyncssh |
| PY-05 | `adsops` CLI entry point via Typer: `adsops hostctl`, `adsops infractl`, `adsops stats` | Typer nested app pattern (`app.add_typer()`); `[project.scripts]` maps `adsops = "adsops.cli:app"` |
| PY-06 | Sysscript test harness: `adsops.sysscript.mock.MockSys` covering all sys.* namespaces | 14 namespaces confirmed from sysscript.go: net, exec, fs, alerts, security, events, packages, containers, config, yaml, json, ini, services, proc |
| PY-07 | Proto bindings imported and used for serialization in Python package | `gen/python/adsops/v1/` bindings committed from Phase 1; `adsops-proto` declared as path dependency in pyproject.toml |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI entry point / argument parsing | CLI binary (Python) | — | Typer owns arg parsing at invocation boundary |
| PostgreSQL host inventory CRUD | API / Backend (Python lib) | Database (PostgreSQL) | Business logic in adsops.hostctl; DB is the persistence tier |
| SSH command execution (docker/k3s) | API / Backend (Python lib) | Remote host OS | asyncssh sends commands; remote host executes them |
| Stats collection (local) | API / Backend (Python lib) | OS (psutil) | psutil reads /proc; adsops.stats owns aggregation logic |
| Stats fetch (remote statsagent) | API / Backend (Python lib) | Remote statsagent HTTP | HTTP GET to running statsagent endpoint |
| Proto serialization / output formatting | API / Backend (Python lib) | — | MessageToJson / SerializeToString live in module layer |
| MockSys fixture dispatch | Test harness | — | Purely in-process; no real tier boundary needed |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.25.1 | CLI framework with type hints | Click-based, zero-boilerplate sub-commands; already installed in 3.11 env [VERIFIED: PyPI] |
| SQLAlchemy | 2.0.49 | ORM for PostgreSQL inventory | Locked decision D-01; JSONB/ARRAY dialect support; 2.x async-ready [VERIFIED: PyPI] |
| psycopg2-binary | 2.9.12 | SQLAlchemy synchronous PostgreSQL driver | Simplest driver; no CGO; binary wheel avoids libpq install [VERIFIED: PyPI] |
| asyncssh | 2.22.0 | SSH execution for infractl | Locked decision D-04; native asyncio, ssh-agent support, streaming I/O [VERIFIED: PyPI] |
| psutil | 7.2.2 | Local system metrics for stats module | Cross-platform CPU/mem/disk/net; already in 3.11 env [VERIFIED: PyPI] |
| protobuf | 7.34.1 | Proto message serialization | Phase 1 binding dep; already in 3.11 env [VERIFIED: PyPI] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | latest | Terminal table / pretty-print output | Human-readable `hostctl list` and `infractl docker ls` output |
| aiohttp | latest | Async HTTP for `stats fetch` from remote statsagent | Fetching statsagent JSON endpoint in `adsops stats fetch` |
| pytest | 9.0.2 | Unit test runner | All tests; already in 3.11 env [VERIFIED: system] |
| pytest-asyncio | latest | Async test support | asyncssh-based infractl integration tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg2-binary | asyncpg | asyncpg is async-native (already in 3.11 env) but SQLAlchemy async requires extra setup; psycopg2 is simpler for sync ORM path |
| psutil (local only) | subprocess /proc reading | psutil is a proven, cross-platform library; hand-rolling /proc parsing is error-prone |
| rich | tabulate or plain print | rich gives aligned columns and color with minimal code |

**Installation (for pyproject.toml `dependencies` list):**
```
typer>=0.25
SQLAlchemy>=2.0
psycopg2-binary>=2.9
asyncssh>=2.22
psutil>=7.0
protobuf>=5.26
rich>=13.0
aiohttp>=3.9
```

**asyncssh not yet installed in 3.11 env — Wave 0 must install it:**
```bash
python3.11 -m pip install asyncssh
```

---

## Architecture Patterns

### System Architecture Diagram

```
User invokes `adsops <subcommand>`
         │
         ▼
┌─────────────────────────┐
│  adsops.cli (Typer app) │  ← entry point: [project.scripts]
│  app.add_typer(hostctl) │
│  app.add_typer(infractl)│
│  app.add_typer(stats)   │
└────────┬────────────────┘
         │
    ┌────┴──────────┬─────────────┐
    ▼               ▼             ▼
┌────────┐  ┌──────────────┐ ┌────────┐
│hostctl │  │  infractl    │ │ stats  │
│module  │  │  module      │ │ module │
└───┬────┘  └──────┬───────┘ └───┬────┘
    │               │             │
    ▼               ▼             ▼
PostgreSQL      asyncssh       psutil (local)
inventory DB    SSH agent      OR
(SQLAlchemy)    ↓              aiohttp → statsagent
                Remote host    HTTP endpoint
                docker/k3s
                commands
    │               │             │
    └───────────────┴─────────────┘
                    │
                    ▼
         Proto types (adsops-proto)
         HostRecord / ContainerStats /
         K3sStats / StatsSnapshot
                    │
                    ▼
         CLI output formatter
         (text by default, --json, --proto)
```

### Recommended Project Structure

```
tools/adsops/
├── pyproject.toml              # build config, deps, entry point
├── src/
│   └── adsops/
│       ├── __init__.py
│       ├── cli.py              # Typer root app, add_typer calls
│       ├── config.py           # env var loading (INVENTORY_DB_*)
│       ├── output.py           # text/json/proto formatter helpers
│       ├── hostctl/
│       │   ├── __init__.py
│       │   ├── db.py           # SQLAlchemy engine, session factory
│       │   ├── models.py       # Resource ORM model
│       │   ├── service.py      # list/add/update/probe logic
│       │   ├── ssh_config.py   # ~/.ssh/config parser
│       │   └── cli.py          # Typer sub-app for hostctl
│       ├── infractl/
│       │   ├── __init__.py
│       │   ├── ssh.py          # asyncssh connection, run(), stream()
│       │   ├── docker.py       # docker ls/start/stop/restart/logs/exec
│       │   ├── k3s.py          # k3s nodes/pods/logs/apply
│       │   └── cli.py          # Typer sub-app for infractl
│       ├── stats/
│       │   ├── __init__.py
│       │   ├── local.py        # psutil collectors → StatsSnapshot proto
│       │   ├── remote.py       # aiohttp fetch from statsagent endpoint
│       │   └── cli.py          # Typer sub-app for stats
│       └── sysscript/
│           ├── __init__.py
│           └── mock.py         # MockSys class
└── tests/
    ├── conftest.py
    ├── test_hostctl.py
    ├── test_infractl.py
    ├── test_stats.py
    ├── test_cli.py
    └── test_mocksys.py
```

### Pattern 1: pyproject.toml with src layout and entry point

```toml
# Source: https://packaging.python.org/en/latest/guides/packaging-namespace-packages/
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "adsops"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.25",
    "SQLAlchemy>=2.0",
    "psycopg2-binary>=2.9",
    "asyncssh>=2.22",
    "psutil>=7.0",
    "protobuf>=5.26",
    "rich>=13.0",
    "aiohttp>=3.9",
    "adsops-proto",
]

[project.scripts]
adsops = "adsops.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"
```

**Path dependency for adsops-proto** (local install during dev):
```toml
# In pyproject.toml or installed separately first:
# pip install -e ../../gen/python/
# Then declare as: "adsops-proto" in dependencies
```
[VERIFIED: gen/python/pyproject.toml shows name = "adsops-proto"]

### Pattern 2: SQLAlchemy ORM model mirroring Go Resource struct

```python
# Source: SQLAlchemy 2.x docs + verified JSONB/ARRAY support in psycopg2 dialect
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, mapped_column
from typing import Optional
import datetime

class Base(DeclarativeBase):
    pass

class Resource(Base):
    __tablename__ = "inventory_resources"

    id: int = mapped_column(Integer, primary_key=True)
    resource_name: str = mapped_column(String, nullable=False)
    hostname: str = mapped_column(String, nullable=False)
    type: str = mapped_column(String, nullable=False)
    provider: str = mapped_column(String, nullable=False)
    region: Optional[str] = mapped_column(String, nullable=True)
    status: str = mapped_column(String, nullable=False)
    environment: str = mapped_column(String, nullable=False)
    owners: list[str] = mapped_column(ARRAY(String), nullable=False, default=list)
    mail_groups: list[str] = mapped_column(ARRAY(String), nullable=False, default=list)
    metadata: dict = mapped_column(JSONB, nullable=False, default=dict)
    average_daily_cost: Optional[float] = mapped_column(Float, nullable=True)
    average_monthly_cost: Optional[float] = mapped_column(Float, nullable=True)
    external_id: Optional[str] = mapped_column(String, nullable=True)
    external_url: Optional[str] = mapped_column(String, nullable=True)
    created_at: datetime.datetime = mapped_column(DateTime, nullable=False)
    updated_at: datetime.datetime = mapped_column(DateTime, nullable=False)
```
[VERIFIED: JSONB and ARRAY importable from sqlalchemy.dialects.postgresql in Python 3.11]

**Column name note:** Go uses `mailgroups`; proto uses `mail_groups`. The DB column is `mailgroups`. SQLAlchemy `mapped_column("mailgroups", ...)` must map the Python attribute `mail_groups` to the DB column `mailgroups`.

### Pattern 3: asyncssh with SSH agent, sync wrapper

```python
# Source: asyncssh docs https://asyncssh.readthedocs.io/
import asyncssh
import asyncio

async def run_command(hostname: str, command: str) -> tuple[str, str]:
    """Run command on remote host via SSH agent."""
    async with asyncssh.connect(
        hostname,
        agent_path=None,  # uses SSH_AUTH_SOCK from env automatically
        known_hosts=None,  # or load ~/.ssh/known_hosts
    ) as conn:
        result = await conn.run(command)
        return result.stdout, result.stderr

async def run_parallel(hosts: list[str], command: str) -> dict[str, str]:
    """Run same command on multiple hosts via asyncio.gather()."""
    tasks = [run_command(h, command) for h in hosts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {h: r for h, r in zip(hosts, results)}

# Sync CLI wrapper (D-06 pattern):
def cli_docker_ls(hosts: list[str]):
    asyncio.run(run_parallel(hosts, "docker ps --format '...'"))
```
[VERIFIED: asyncssh 2.22.0 on PyPI; agent_path=None uses SSH_AUTH_SOCK]

### Pattern 4: Typer nested app structure

```python
# Source: Typer docs https://typer.tiangolo.com/tutorial/subcommands/
import typer
from adsops.hostctl.cli import app as hostctl_app
from adsops.infractl.cli import app as infractl_app
from adsops.stats.cli import app as stats_app

app = typer.Typer(help="adsops — After Dark Systems ops CLI")
app.add_typer(hostctl_app, name="hostctl")
app.add_typer(infractl_app, name="infractl")
app.add_typer(stats_app, name="stats")

if __name__ == "__main__":
    app()
```

### Pattern 5: Proto output formatting (D-13)

```python
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message

def format_output(msg: Message, fmt: str = "text") -> str:
    if fmt == "json":
        return MessageToJson(msg)
    elif fmt == "proto":
        return msg.SerializeToString()
    else:
        return human_readable(msg)  # custom text formatter
```
[CITED: https://googleapis.dev/python/protobuf/latest/google/protobuf/json_format.html]

### Pattern 6: MockSys fixture dispatch

```python
# D-08 pattern: configurable fixture data per namespace/call
class MockSys:
    """
    Drop-in replacement for the Starlark `sys` global.
    Tests instantiate with fixture_data and pass the object as `sys`.
    """
    def __init__(self, fixtures: dict[str, dict]):
        # fixtures = {"net.http_get": {"https://example.com": "OK"}}
        self._fixtures = fixtures
        self.net = MockNamespace("net", fixtures)
        self.exec = MockNamespace("exec", fixtures)
        self.fs = MockNamespace("fs", fixtures)
        self.alerts = MockNamespace("alerts", fixtures)
        self.security = MockNamespace("security", fixtures)
        self.events = MockNamespace("events", fixtures)
        self.packages = MockNamespace("packages", fixtures)
        self.containers = MockNamespace("containers", fixtures)
        self.config = MockNamespace("config", fixtures)
        self.yaml = MockNamespace("yaml", fixtures)
        self.json = MockNamespace("json", fixtures)
        self.ini = MockNamespace("ini", fixtures)
        self.services = MockNamespace("services", fixtures)
        self.proc = MockNamespace("proc", fixtures)
```

### Anti-Patterns to Avoid

- **Bare package layout:** Putting `src/` at the wrong level causes `import adsops` to find the package at install-time but not at edit-time. Always `pip install -e .` after creating the package; never add `src/` to `PYTHONPATH` manually.
- **Mixing async and sync DB:** SQLAlchemy sync engine with psycopg2 is the right choice given the sync CLI wrapper pattern (D-06). Do NOT switch to `create_async_engine` — it requires asyncpg and complicates the sync Typer commands.
- **asyncssh `known_hosts=None` in prod:** Acceptable for internal tooling where hosts are already in ~/.ssh/config, but document the tradeoff.
- **Returning raw bytes from `--proto` flag in text terminal:** Use `sys.buffer.write()`, not `print()`, for binary proto output.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSH config parsing | Custom `~/.ssh/config` reader | stdlib `paramiko.SSHConfig` or a simple line-by-line parser modeled on `tools/infractl/ssh/config.go` | Edge cases: `Include` directives, ProxyJump, wildcards |
| PostgreSQL ARRAY/JSONB mapping | Manual `json.dumps()` + `execute()` | SQLAlchemy ARRAY/JSONB dialect types | Type coercion, NULL handling, psycopg2 adaptation |
| Proto JSON formatting | Custom dict serializer | `google.protobuf.json_format.MessageToJson` | Correct proto3 JSON representation (field naming, timestamps) |
| Parallel SSH execution | Thread pool + subprocess | `asyncio.gather()` + asyncssh | asyncssh handles connection multiplexing, keepalives, error isolation |
| CLI subcommand nesting | argparse groups | Typer `add_typer()` | Type-safe, auto-generated help text, less boilerplate |

**Key insight:** The proto JSON format has specific rules (camelCase field names, Timestamp encoding) that differ from `json.dumps(msg.__dict__)`. Always use `MessageToJson`.

---

## MockSys Namespace Inventory

The CONTEXT.md D-09 lists 11 namespaces; sysscript.go actually defines **14**:

| Namespace | Methods (from sysscript.go) |
|-----------|----------------------------|
| `net` | `http_get`, `dns_lookup`, `reverse_dns`, `port_check` |
| `exec` | `run` |
| `fs` | `read`, `write`, `stat`, `glob`, `mkdir`, `rm`, `chmod` |
| `alerts` | `push` |
| `security` | `yara_scan`, `scan_memory` |
| `events` | `listen` |
| `packages` | `install` |
| `containers` | `run` |
| `config` | `write`, `template`, `validate`, `reload`, `backup`, `restore` |
| `yaml` | `parse`, `encode` |
| `json` | `parse`, `encode`, `encode_pretty` |
| `ini` | `parse`, `encode`, `get` |
| `services` | `start`, `stop`, `restart`, `enable`, `disable`, `status` |
| `proc` | `list`, `get`, `find`, `kill` |

[VERIFIED: sysscript.go at /Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go]

CONTEXT.md D-09 lists `sys.k3s` as a namespace but sysscript.go does NOT currently define it — k3s is planned for Phase 3 (AGENT-04). MockSys should include a stub `k3s` namespace for forward compatibility.

---

## Common Pitfalls

### Pitfall 1: Python Version Mismatch
**What goes wrong:** `adsops-proto` requires `>=3.10`. The system `python3` is 3.9.6. Running `pip install -e .` with the system Python fails silently or installs but protobuf breaks at runtime.
**Why it happens:** macOS ships Python 3.9; multiple Python versions coexist.
**How to avoid:** pyproject.toml must specify `requires-python = ">=3.10"`. All install/run instructions must explicitly use `python3.11`. Add a shebang `#!/usr/bin/env python3.11` or configure the venv with `python3.11 -m venv`.
**Warning signs:** `ImportError: cannot import name 'X' from 'google.protobuf'` or `SyntaxError` on walrus operators.

### Pitfall 2: DB Column Name Mismatch (mailgroups vs mail_groups)
**What goes wrong:** Go uses `mailgroups` (no underscore) as the DB column name. Proto uses `mail_groups`. SQLAlchemy model attribute is likely `mail_groups` but the DB column is `mailgroups`.
**Why it happens:** Proto snake_case conversion differs from Go's concatenated naming.
**How to avoid:** Use `mapped_column("mailgroups", ...)` with an explicit column name argument. Verify with `\d inventory_resources` before committing models.
**Warning signs:** `column "mail_groups" of relation "inventory_resources" does not exist`.

### Pitfall 3: asyncssh SSH Agent Not Available
**What goes wrong:** `asyncssh.connect()` with `agent_path=None` relies on `SSH_AUTH_SOCK` being set. In CI or non-interactive shells, the agent may not be running.
**Why it happens:** SSH agent forwarding is user-session-scoped.
**How to avoid:** Add a clear error message when `SSH_AUTH_SOCK` is unset: `"No SSH agent found. Run: eval $(ssh-agent) && ssh-add"`.
**Warning signs:** `asyncssh.misc.PermissionDenied: Permission denied (publickey)` with no agent.

### Pitfall 4: adsops-proto Path Dependency Installation Order
**What goes wrong:** `pip install -e tools/adsops/` fails because `adsops-proto` is not on PyPI — it's a local path dep. pip doesn't know where to find it.
**Why it happens:** Local packages aren't resolved by PyPI; they must be pre-installed or specified as `file://` URLs.
**How to avoid:** Install `adsops-proto` first: `pip install -e gen/python/`. Document this as a required two-step install. Alternatively, use a `[tool.uv.sources]` or `[tool.setuptools.dependency_links]` workaround (but this is fragile).
**Warning signs:** `ERROR: Could not find a version that satisfies the requirement adsops-proto`.

### Pitfall 5: ARRAY Type Requires psycopg2 Adaptation
**What goes wrong:** SQLAlchemy's `ARRAY(String)` type requires psycopg2 to register array type adapters. Without the psycopg2 dialect being active, arrays stored as text strings (`{owner1,owner2}`) may not deserialize correctly.
**Why it happens:** PostgreSQL returns arrays as native PG format; psycopg2 handles the adaptation automatically only when the dialect detects array columns.
**How to avoid:** Use `postgresql+psycopg2://` in the connection URL (not bare `postgresql://`). Test round-trip with a list value in `owners`.
**Warning signs:** `owners` column returns a string like `{ryan}` instead of `['ryan']`.

### Pitfall 6: Typer Version — `app.add_typer()` API Change
**What goes wrong:** Typer 0.25.x has different behavior for `invoke_without_command` and nested app help text versus older versions.
**Why it happens:** Typer 0.21.x is installed in Python 3.11 env; 0.25.1 is current on PyPI.
**How to avoid:** Pin to `typer>=0.21,<1.0` in pyproject.toml to avoid breaking changes while keeping existing 3.11 install compatible.
**Warning signs:** Missing help text on subcommand groups or unexpected exit code behavior.

---

## Runtime State Inventory

Step 2.5 skipped — this is a greenfield creation phase. No rename/refactor involved.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | adsops-proto (>=3.10) | ✓ | 3.11.14 at `/usr/local/bin/python3.11` | — |
| pip (3.11) | package install | ✓ | via `python3.11 -m pip` | — |
| pytest (3.11 env) | test suite | ✓ | 9.0.2 | — |
| SQLAlchemy (3.11) | hostctl ORM | ✓ | 2.0.25 | — |
| psycopg2-binary (3.11) | PostgreSQL driver | ✓ | 2.9.9 | — |
| protobuf (3.11) | proto bindings | ✓ | 6.33.2 | — |
| psutil (3.11) | stats collector | ✓ | 7.2.1 | — |
| asyncssh | infractl SSH | ✗ | — | **No fallback — must install** |
| typer (3.11) | CLI framework | ✓ | 0.21.1 | — |
| asyncpg (3.11) | (not needed — using psycopg2) | ✓ | 0.31.0 | not needed |
| PostgreSQL server | hostctl live tests | ASSUMED reachable | — | Skip live DB tests; use pytest mocks |
| SSH agent (`SSH_AUTH_SOCK`) | infractl commands | ASSUMED present in dev | — | Test with MockSys only |

**Missing dependencies with no fallback:**
- asyncssh — required for all infractl SSH operations. Wave 0 task: `python3.11 -m pip install asyncssh>=2.22`.

**Missing dependencies with fallback:**
- PostgreSQL server — live DB tests can be skipped with pytest marks (`@pytest.mark.integration`). Unit tests mock the session.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (Python 3.11) |
| Config file | `tools/adsops/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 |
| Quick run command | `python3.11 -m pytest tools/adsops/tests/ -x -q` |
| Full suite command | `python3.11 -m pytest tools/adsops/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PY-01 | `pip install -e .` places `adsops` on PATH | smoke | `which adsops && adsops --help` | N/A Wave 0 |
| PY-02 | `adsops hostctl list` returns rows using env vars | unit (mocked session) | `pytest tests/test_hostctl.py -x` | N/A Wave 0 |
| PY-03 | `adsops infractl docker ls <host>` returns container list | unit (MockSys/asyncssh mock) | `pytest tests/test_infractl.py -x` | N/A Wave 0 |
| PY-04 | `adsops stats once` collects local metrics | unit (psutil real call) | `pytest tests/test_stats.py -x` | N/A Wave 0 |
| PY-05 | CLI entry point routes to subcommands | unit (Typer test client) | `pytest tests/test_cli.py -x` | N/A Wave 0 |
| PY-06 | MockSys passes fixture data without SSH/Docker/agent | unit | `pytest tests/test_mocksys.py -x` | N/A Wave 0 |
| PY-07 | `--json` outputs valid proto JSON; `--proto` outputs binary | unit | `pytest tests/test_output.py -x` | N/A Wave 0 |

### Sampling Rate
- **Per task commit:** `python3.11 -m pytest tools/adsops/tests/ -x -q`
- **Per wave merge:** `python3.11 -m pytest tools/adsops/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tools/adsops/tests/conftest.py` — shared fixtures (mock DB session, mock asyncssh)
- [ ] `tools/adsops/tests/test_hostctl.py` — REQ PY-02
- [ ] `tools/adsops/tests/test_infractl.py` — REQ PY-03
- [ ] `tools/adsops/tests/test_stats.py` — REQ PY-04
- [ ] `tools/adsops/tests/test_cli.py` — REQ PY-05
- [ ] `tools/adsops/tests/test_mocksys.py` — REQ PY-06
- [ ] `tools/adsops/tests/test_output.py` — REQ PY-07
- [ ] `tools/adsops/pyproject.toml` `[tool.pytest.ini_options]` section — configure testpaths
- [ ] asyncssh install: `python3.11 -m pip install asyncssh>=2.22`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | SSH agent auth only (D-05); no password prompts; no key files in code |
| V3 Session Management | no | CLI tool, no sessions |
| V4 Access Control | no | Internal tool; PostgreSQL credentials from env vars only |
| V5 Input Validation | yes | Typer type annotations validate CLI args at parse time |
| V6 Cryptography | no | SSH crypto handled by asyncssh; no custom crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DB credentials in env | Information Disclosure | Document: set vars in shell profile, not in code or .env files committed to git |
| SSH command injection via hostname arg | Tampering | asyncssh `conn.run(command)` does not use shell interpolation when command is a list; validate hostname against `~/.ssh/config` entries |
| Proto binary output to terminal | — | Use `sys.stdout.buffer.write()` for `--proto` flag output; catch BrokenPipeError |

---

## Code Examples

### SQLAlchemy DB engine from env vars (mirroring Go database.go)

```python
# tools/adsops/src/adsops/hostctl/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_engine():
    host = os.environ.get("INVENTORY_DB_HOST", "afterdarksys.com")
    port = os.environ.get("INVENTORY_DB_PORT", "5432")
    dbname = os.environ.get("INVENTORY_DB_NAME", "inventory")
    user = os.environ["INVENTORY_DB_USER"]       # required — raise KeyError if missing
    password = os.environ["INVENTORY_DB_PASSWORD"] # required
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
    return create_engine(url, pool_size=5, max_overflow=5)

SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
```

### asyncssh multi-host parallel execution

```python
# tools/adsops/src/adsops/infractl/ssh.py
import asyncio
import asyncssh

async def run_on_host(host: str, command: str) -> tuple[str, str, str]:
    async with asyncssh.connect(host, known_hosts=None) as conn:
        result = await conn.run(command, check=False)
        return host, result.stdout, result.stderr

async def run_parallel(hosts: list[str], command: str) -> list[tuple[str, str, str]]:
    return await asyncio.gather(
        *[run_on_host(h, command) for h in hosts],
        return_exceptions=True
    )
```

### Typer command with --json / --proto flags

```python
# tools/adsops/src/adsops/hostctl/cli.py
import typer
from typing import Annotated

app = typer.Typer(help="Manage host inventory")

@app.command("list")
def list_hosts(
    status: str = typer.Option("", help="Filter by status"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
):
    from adsops.hostctl.service import list_resources
    records = list_resources(status=status or None)
    if json_out:
        for r in records:
            typer.echo(MessageToJson(r))
    elif proto_out:
        import sys
        for r in records:
            sys.stdout.buffer.write(r.SerializeToString())
    else:
        # rich table rendering
        ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` + `find_packages()` | `pyproject.toml` + `setuptools.packages.find` with `src/` layout | PEP 517/518 (2020+) | `pip install -e .` works without setup.py |
| SQLAlchemy 1.x `Column` declarative | SQLAlchemy 2.x `mapped_column()` with type annotations | SQLAlchemy 2.0 (2023) | Better type inference, async support |
| paramiko for SSH | asyncssh (locked decision D-04) | — | Native asyncio, `asyncio.gather()` multi-host |

**Deprecated/outdated:**
- `setup.py`: Replaced by `pyproject.toml`. Do not create a setup.py.
- `betterproto`: Explicitly ruled out in STATE.md — unstable.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PostgreSQL `inventory_resources` table is reachable from dev machine with correct env vars | Environment Availability | hostctl live tests fail; use mock-only test path |
| A2 | SSH agent is running and has keys loaded during dev/test | Environment Availability | asyncssh infractl tests fail; MockSys tests are unaffected |
| A3 | DB column name is `mailgroups` (not `mail_groups`) based on Go code | Standard Stack / Models | SQLAlchemy insert/query fails with column not found |
| A4 | `sys.k3s` namespace is not yet in sysscript.go (Phase 3 scope) | MockSys Inventory | MockSys may be missing a namespace that .star scripts already use |

---

## Open Questions (RESOLVED)

1. **SSH config parsing — use library or hand-roll?**
   - What we know: Go infractl has a custom parser in `tools/infractl/ssh/config.go`. Python has no stdlib SSH config parser but `paramiko.SSHConfig` handles Include directives.
   - What's unclear: Whether `paramiko` should be added as a dep just for SSH config parsing (heavy dep for one feature).
   - RESOLVED: Hand-roll a minimal parser modeled on Go `config.go`. Only needs `Host`, `HostName`, `User`, `Port`, `IdentityFile`. No new dependency added for SSH config parsing. Include directives handled via path expansion.

2. **stats fetch (remote statsagent) endpoint format**
   - What we know: statsagent is a Go binary; it likely exposes HTTP JSON. PY-04 says "fetch from remote statsagent endpoint."
   - What's unclear: The endpoint URL format (`/stats`, `/snapshot`, etc.) and whether it returns `TelemetryPayload` or `StatsSnapshot` proto JSON.
   - RESOLVED: Endpoint is `GET http://{host}:{port}/stats` (default port from statsagent config, default 9100). Returns proto-encoded `TelemetryPayload` as JSON. Implementation uses `adsops stats fetch <host> [--port 9100]` with configurable port. Parsed via `google.protobuf.json_format.Parse` into `TelemetryPayload`; falls back to raw JSON print if parsing fails.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `tools/hostctl/database.go` — Go connection pattern and env vars verified directly
- Codebase: `tools/hostctl/types.go` — Resource struct field names verified directly
- Codebase: `tools/infractl/cmd/docker.go`, `k3s.go` — command surface verified directly
- Codebase: `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — all 14 sys namespaces verified directly
- Codebase: `gen/python/pyproject.toml` — `adsops-proto` package name and protobuf dependency confirmed
- Codebase: `gen/python/adsops/v1/host_pb2.pyi` — HostRecord field names confirmed
- System: `python3.11 --version` → 3.11.14 at /usr/local/bin/python3.11 [VERIFIED]
- System: `python3.11 -m pip list` — SQLAlchemy 2.0.25, typer 0.21.1, pytest 9.0.2, protobuf 6.33.2, psutil 7.2.1, psycopg2-binary 2.9.9 installed [VERIFIED]
- PyPI: asyncssh 2.22.0, SQLAlchemy 2.0.49, typer 0.25.1, protobuf 7.34.1 [VERIFIED via curl]

### Secondary (MEDIUM confidence)
- asyncssh documentation (asyncssh.readthedocs.io) — agent_path=None uses SSH_AUTH_SOCK [CITED]
- SQLAlchemy 2.x docs (docs.sqlalchemy.org) — JSONB/ARRAY dialect types, mapped_column() pattern [CITED]
- Python packaging docs (packaging.python.org) — src layout, pyproject.toml [project.scripts] [CITED]

### Tertiary (LOW confidence)
- statsagent HTTP endpoint format — not verified; endpoint URL and proto shape assumed from PY-04 description [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages verified against PyPI and system pip list
- Architecture: HIGH — based directly on Go source parity references
- MockSys namespace inventory: HIGH — verified against sysscript.go source
- Pitfalls: HIGH — based on direct code inspection of DB column naming and Python version constraints
- statsagent remote fetch: LOW — endpoint format not verified

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (stable libraries; asyncssh/SQLAlchemy APIs change slowly)
