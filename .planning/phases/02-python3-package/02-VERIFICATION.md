---
phase: 02-python3-package
verified: 2026-05-04T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
deferred: []
human_verification: []
---

# Phase 2: Python3 Package Verification Report

**Phase Goal:** Users can run `adsops hostctl list`, `adsops infractl docker ls <host>`, and `adsops stats once` from a pip-installed Python package
**Verified:** 2026-05-04
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `pip install -e tools/adsops/` succeeds and places `adsops` binary on PATH | VERIFIED | `pip show adsops` returns Name: adsops Version: 0.1.0; entry point `adsops = "adsops.cli:app"` in pyproject.toml |
| 2  | `adsops hostctl list` queries PostgreSQL via SQLAlchemy using INVENTORY_DB_* env vars | VERIFIED | `service.py` uses `get_session()` → `get_db_url()` → `config.py` reads INVENTORY_DB_{HOST,PORT,NAME,USER,PASSWORD}; parameterized SQLAlchemy queries confirmed |
| 3  | `adsops hostctl list --json` outputs proto JSON via MessageToJson | VERIFIED | `output.py` calls `MessageToJson(msg)` for json fmt; `test_cli_json_output` passes; manual check confirmed valid JSON output |
| 4  | `adsops hostctl probe <hostname>` attempts SSH connection and reports success/failure | VERIFIED | `service.py` `probe_host()` calls `asyncio.run(_probe(hostname))` with `asyncssh.connect`; `test_probe_host_reachable` and `test_probe_host_unreachable` pass |
| 5  | `adsops infractl docker ls <host>` executes docker ps over SSH via asyncssh | VERIFIED | `docker.py` `docker_ls()` calls `run_sync(host, cmd)` → `asyncssh.connect`; `test_docker_ls_returns_output` passes |
| 6  | `adsops infractl k3s pods <host>` executes k3s kubectl get pods over SSH | VERIFIED | `k3s.py` `k3s_pods()` calls `run_sync(host, "k3s kubectl get pods ...")` via `ssh.py`; `test_k3s_pods_all_namespaces` passes |
| 7  | Multi-host execution runs in parallel via asyncio.gather() | VERIFIED | `ssh.py` `run_parallel()` uses `asyncio.gather(*[_run(h) for h in hosts], return_exceptions=True)`; `test_docker_ls_multi_host` passes |
| 8  | SSH agent auth required; clear error when SSH_AUTH_SOCK unset | VERIFIED | `ssh.py` checks `os.environ.get("SSH_AUTH_SOCK")`; raises `RuntimeError("No SSH agent found. Run: eval $(ssh-agent) && ssh-add")`; `test_ssh_agent_check_raises_without_sock` passes |
| 9  | `adsops stats once` collects local CPU/mem/disk/net metrics via psutil | VERIFIED | `stats/local.py` `collect_once()` calls psutil.cpu_percent, psutil.virtual_memory, psutil.disk_partitions, psutil.net_io_counters; `test_collect_once_returns_snapshot` passes |
| 10 | `adsops stats fetch <host>` retrieves TelemetryPayload from remote statsagent | VERIFIED | `stats/remote.py` `fetch_once()` uses aiohttp to GET `http://{host}:{port}/stats` and parses with `json_format.Parse`; `test_fetch_once_parses_response` passes |
| 11 | MockSys provides all 15 namespaces with fixture-driven responses | VERIFIED | `sysscript/mock.py` `MockSys` instantiates all 15 `MockNamespace` instances (14 verified + k3s stub); `test_mocksys_all_namespaces_exist` passes |
| 12 | `adsops --help` shows hostctl, infractl, and stats subcommands | VERIFIED | `cli.py` conditional imports register all three sub-apps; `test_help_shows_hostctl/infractl/stats` all pass |
| 13 | pytest tools/adsops/tests/ passes with mocked DB/SSH/HTTP | VERIFIED | Full suite: **49 passed, 0 failed in 5.21s** |
| 14 | Proto bindings imported and used for serialization in Python package | VERIFIED | `service.py` imports `from adsops.v1 import host_pb2`; `stats/local.py` imports `from adsops.v1 import stats_pb2`; `stats/remote.py` imports `from adsops.v1 import telemetry_pb2` |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tools/adsops/pyproject.toml` | Package config with deps and entry point | VERIFIED | Contains `adsops = "adsops.cli:app"` and `adsops-proto` dependency |
| `tools/adsops/src/adsops/hostctl/models.py` | SQLAlchemy ORM mirroring Go Resource struct | VERIFIED | `class Resource(Base)`, `__tablename__ = "inventory_resources"`, `mapped_column("mailgroups"`, `mapped_column("metadata"` all present |
| `tools/adsops/src/adsops/hostctl/service.py` | CRUD operations returning HostRecord protos | VERIFIED | `list_resources`, `add_resource`, `update_resource`, `probe_host`, `import_ssh_config` all present; `from adsops.v1 import host_pb2` confirmed |
| `tools/adsops/src/adsops/output.py` | Proto output formatting (text/json/proto) | VERIFIED | `print_proto`, `format_output` with MessageToJson, SerializeToString, sys.stdout.buffer.write all present |
| `tools/adsops/src/adsops/infractl/ssh.py` | asyncssh layer with parallel execution | VERIFIED | `run_command`, `run_parallel`, `stream_command`, `run_sync`, `run_parallel_sync` all present; SSH_AUTH_SOCK guard confirmed |
| `tools/adsops/src/adsops/infractl/docker.py` | Docker commands over SSH | VERIFIED | `docker_ls`, `docker_start`, `docker_stop`, `docker_restart`, `docker_logs`, `docker_exec` all present; input validation via `_SAFE_HOST_RE`/`_SAFE_NAME_RE` |
| `tools/adsops/src/adsops/infractl/k3s.py` | k3s commands over SSH | VERIFIED | `k3s_nodes`, `k3s_pods`, `k3s_logs`, `k3s_apply` all present; `asyncssh.scp` used in `_apply()`; `os.path.basename()` path guard confirmed |
| `tools/adsops/src/adsops/infractl/cli.py` | Typer sub-app with docker and k3s groups | VERIFIED | `docker_app = typer.Typer`, `k3s_app = typer.Typer`, `app.add_typer(docker_app, name="docker")` confirmed |
| `tools/adsops/src/adsops/stats/local.py` | psutil-based local metrics returning StatsSnapshot | VERIFIED | `collect_once()` with `psutil.cpu_percent`, `psutil.virtual_memory`; `from adsops.v1 import stats_pb2` |
| `tools/adsops/src/adsops/stats/remote.py` | aiohttp fetch from statsagent | VERIFIED | `fetch_once()` with `aiohttp.ClientSession`, `json_format.Parse`; `from adsops.v1 import telemetry_pb2` |
| `tools/adsops/src/adsops/sysscript/mock.py` | MockSys with all 15 namespaces | VERIFIED | `class MockSys`, `class MockNamespace`, all 15 namespace attributes present |
| `tools/adsops/tests/test_cli.py` | CLI entry point routing tests for PY-05 | VERIFIED | `test_help_shows_hostctl`, `test_help_shows_infractl`, `test_help_shows_stats`, and 3 more — all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `hostctl/service.py` | `gen/python/adsops/v1/host_pb2.py` | `from adsops.v1 import host_pb2` | WIRED | Import confirmed in file; `HostRecord` constructed and returned |
| `hostctl/db.py` | `config.py` | `from adsops.config import get_db_url` | WIRED | Confirmed in db.py; `get_engine()` calls `create_engine(get_db_url(), ...)` |
| `infractl/docker.py` | `infractl/ssh.py` | `from adsops.infractl.ssh import` | WIRED | `from adsops.infractl.ssh import run_sync, stream_command` confirmed |
| `infractl/cli.py` | `infractl/docker.py` | `from adsops.infractl.docker import` | WIRED | CLI imports docker functions before invoking |
| `stats/local.py` | `gen/python/adsops/v1/stats_pb2.py` | `from adsops.v1 import stats_pb2` | WIRED | Import confirmed; `StatsSnapshot`, `SystemStats`, `DiskStats` etc. all constructed |
| `stats/remote.py` | `gen/python/adsops/v1/telemetry_pb2.py` | `from adsops.v1 import telemetry_pb2` | WIRED | Import confirmed; `Parse(body, telemetry_pb2.TelemetryPayload())` used |
| `cli.py` | all three sub-CLIs | conditional try/except imports | WIRED | All three sub-apps register at import time via `_register()` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `hostctl/service.py` `list_resources` | `rows` | `session.scalars(stmt).all()` on `inventory_resources` | Yes — SQLAlchemy SELECT with dynamic WHERE | FLOWING |
| `stats/local.py` `collect_once` | `snap` | `psutil.cpu_percent()`, `psutil.virtual_memory()`, `psutil.disk_partitions()`, `psutil.net_io_counters()` | Yes — real system calls | FLOWING |
| `stats/remote.py` `fetch_once` | `TelemetryPayload` | `aiohttp GET http://{host}:{port}/stats` parsed via `json_format.Parse` | Yes — live HTTP response | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All imports succeed | `python3.11 -c "from adsops.cli import app; from adsops.hostctl.cli import app; from adsops.infractl.cli import app; from adsops.stats.cli import app; from adsops.sysscript.mock import MockSys"` | `All key imports OK` | PASS |
| Proto JSON output works | `python3.11 -c "from adsops.output import print_proto; from adsops.v1 import host_pb2; ..."` | `proto JSON output OK: {'hostname': 'test'}` | PASS |
| MockSys 15 namespaces | `python3.11 -c "from adsops.sysscript.mock import MockSys, MockNamespace; ..."` | `MockSys: all 15 namespaces verified` | PASS |
| Full test suite | `python3.11 -m pytest tools/adsops/tests/ -v` | `49 passed in 5.21s` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PY-01 | 02-01-PLAN | `tools/adsops/` with pyproject.toml, src layout, pip install -e works | SATISFIED | Package installs, `pip show adsops` confirmed |
| PY-02 | 02-01-PLAN | `adsops.hostctl` module: list, add, update, import-ssh-config, probe | SATISFIED | All 5 commands implemented; 14 passing tests |
| PY-03 | 02-02-PLAN | `adsops.infractl` module: docker (6 cmds) and k3s (4 cmds) over SSH | SATISFIED | All 10 commands implemented; 17 passing tests |
| PY-04 | 02-03-PLAN | `adsops.stats` module: collect once, fetch from remote statsagent | SATISFIED | `collect_once()` and `fetch_once()` implemented; 5 passing tests |
| PY-05 | 02-03-PLAN | `adsops` CLI entry point via Typer: hostctl, infractl, stats subcommands | SATISFIED | All 3 sub-apps registered; 6 CLI routing tests pass |
| PY-06 | 02-03-PLAN | `adsops.sysscript.mock` — Python mock of Starlark sys for .star unit testing | SATISFIED | `MockSys` + `MockNamespace` with 15 namespaces; 7 passing tests |
| PY-07 | 02-01-PLAN, 02-03-PLAN | Proto bindings imported and used for serialization in Python package | SATISFIED | host_pb2, stats_pb2, telemetry_pb2 all imported and used in service/stats layers |

### Anti-Patterns Found

None found. No TODO/FIXME/placeholder comments in implementation files. No stub returns (`return []` / `return {}`) in non-test code. All service functions have real implementations wired to their data sources.

### Human Verification Required

None — all must-haves were verified programmatically.

### Gaps Summary

No gaps. All 14 observable truths verified. All 7 requirement IDs satisfied. 49/49 tests pass. All key links wired. All artifacts substantive with real data flows.

Notable extras delivered beyond the plan spec (not gaps, but additions):
- Input validation with regex allowlists in `docker.py` (`_SAFE_HOST_RE`, `_SAFE_NAME_RE`) per threat model T-02-05
- 2 additional security-focused tests: `test_docker_invalid_container_name_rejected`, `test_docker_invalid_host_rejected`

---

_Verified: 2026-05-04_
_Verifier: Claude (gsd-verifier)_
