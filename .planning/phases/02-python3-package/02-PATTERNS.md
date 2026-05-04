# Phase 2: Python3 Package - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 20 (new files to create)
**Analogs found:** 17 / 20

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `tools/adsops/pyproject.toml` | config | — | `gen/python/pyproject.toml` | exact |
| `tools/adsops/src/adsops/__init__.py` | config | — | `gen/python/adsops/__init__.py` | exact |
| `tools/adsops/src/adsops/cli.py` | cli-root | request-response | `opsctl.py` (argparse root) | role-match |
| `tools/adsops/src/adsops/config.py` | utility | request-response | `scripts/aftercloud/adsops_config.py` | role-match |
| `tools/adsops/src/adsops/output.py` | utility | transform | `scripts/python/common.py` (format_table) | partial-match |
| `tools/adsops/src/adsops/hostctl/models.py` | model | CRUD | `tools/hostctl/types.go` (Resource struct) | role-match |
| `tools/adsops/src/adsops/hostctl/db.py` | service | CRUD | `tools/hostctl/database.go` (initDB/getDB) | role-match |
| `tools/adsops/src/adsops/hostctl/service.py` | service | CRUD | `tools/hostctl/database.go` (list/insert/update) | role-match |
| `tools/adsops/src/adsops/hostctl/ssh_config.py` | utility | file-I/O | `tools/infractl/ssh/config.go` | role-match |
| `tools/adsops/src/adsops/hostctl/cli.py` | cli-sub | request-response | `tools/hostctl/commands.go` | role-match |
| `tools/adsops/src/adsops/infractl/ssh.py` | service | request-response | `tools/infractl/cmd/docker.go` (dockerRun/dockerStream) | role-match |
| `tools/adsops/src/adsops/infractl/docker.py` | service | request-response | `tools/infractl/cmd/docker.go` | exact |
| `tools/adsops/src/adsops/infractl/k3s.py` | service | request-response | `tools/infractl/cmd/k3s.go` | exact |
| `tools/adsops/src/adsops/infractl/cli.py` | cli-sub | request-response | `tools/infractl/cmd/docker.go` + `k3s.go` | role-match |
| `tools/adsops/src/adsops/stats/local.py` | service | batch | `tools/statsagent/collectors/docker.go` | partial-match |
| `tools/adsops/src/adsops/stats/remote.py` | service | request-response | `scripts/python/test_central_auth.py` (_request method) | partial-match |
| `tools/adsops/src/adsops/stats/cli.py` | cli-sub | request-response | `tools/hostctl/commands.go` | role-match |
| `tools/adsops/src/adsops/sysscript/mock.py` | utility | event-driven | no analog — new pattern | none |
| `tools/adsops/tests/conftest.py` | test | — | `scripts/python/test_central_auth.py` | partial-match |
| `tools/adsops/tests/test_*.py` | test | — | `scripts/python/test_central_auth.py` | partial-match |

---

## Pattern Assignments

### `tools/adsops/pyproject.toml` (config)

**Analog:** `gen/python/pyproject.toml`

**Full analog** (lines 1-14):
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "adsops-proto"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["protobuf>=5.26"]

[tool.setuptools.packages.find]
where = ["."]
include = ["adsops*"]
```

**Divergences for `tools/adsops/pyproject.toml`:**
- `name = "adsops"`, `requires-python = ">=3.10"`
- `where = ["src"]` (src layout, unlike gen/python which uses flat layout)
- Add `[project.scripts]` section: `adsops = "adsops.cli:app"`
- Full dependencies list: typer, SQLAlchemy, psycopg2-binary, asyncssh, psutil, protobuf, rich, aiohttp, adsops-proto
- Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`

**pyproject.toml template to write:**
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "adsops"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.21",
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

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

### `tools/adsops/src/adsops/config.py` (utility, env var loading)

**Analog:** `scripts/aftercloud/adsops_config.py`

**Env var pattern** (adsops_config.py lines 140-143):
```python
env_key = f"ADSOPS_{section.upper()}_{key.upper()}"
env_value = os.environ.get(env_key)
if env_value:
    return env_value
```

**Error-on-missing pattern** (adsops_config.py lines 114-117):
```python
try:
    with open(self.config_path) as f:
        self._config = json.load(f)
except (json.JSONDecodeError, IOError) as e:
    speak(f"Warning: Could not load config: {e}")
```

**Pattern for `config.py`** — mirror Go database.go env var pattern (lines 22-32 of database.go):
```python
# tools/adsops/src/adsops/config.py
import os

def get_db_url() -> str:
    """Build PostgreSQL connection URL from env vars matching Go hostctl."""
    host = os.environ.get("INVENTORY_DB_HOST", "afterdarksys.com")
    port = os.environ.get("INVENTORY_DB_PORT", "5432")
    dbname = os.environ.get("INVENTORY_DB_NAME", "inventory")
    user = os.environ.get("INVENTORY_DB_USER")
    password = os.environ.get("INVENTORY_DB_PASSWORD")
    if not user:
        raise RuntimeError("INVENTORY_DB_USER environment variable is required")
    if not password:
        raise RuntimeError("INVENTORY_DB_PASSWORD environment variable is required")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
```

---

### `tools/adsops/src/adsops/cli.py` (cli-root, Typer app)

**Analog:** `opsctl.py` (argparse-based root dispatcher, lines 1-100)

**Root dispatcher pattern** (opsctl.py lines 28-44 — module routing):
```python
import argparse
import sys

# opsctl dispatches to sub-modules by name
# Python equivalent uses Typer add_typer() instead of argparse subparsers
```

**Typer root pattern to use** (from RESEARCH.md Pattern 4):
```python
# tools/adsops/src/adsops/cli.py
import typer
from adsops.hostctl.cli import app as hostctl_app
from adsops.infractl.cli import app as infractl_app
from adsops.stats.cli import app as stats_app

app = typer.Typer(help="adsops — After Dark Systems ops CLI", no_args_is_help=True)
app.add_typer(hostctl_app, name="hostctl")
app.add_typer(infractl_app, name="infractl")
app.add_typer(stats_app, name="stats")

if __name__ == "__main__":
    app()
```

---

### `tools/adsops/src/adsops/output.py` (utility, transform)

**Analog:** `scripts/python/common.py` (format_table, lines 111-116)

**Table format pattern** (common.py lines 111-116):
```python
def format_table(headers: list[str], rows: list[list[str]], separator: str = "\t") -> str:
    """Format data as a simple table."""
    lines = [separator.join(headers)]
    for row in rows:
        lines.append(separator.join(str(cell) for cell in row))
    return "\n".join(lines)
```

**Pattern for `output.py`** — extend this with proto support (D-13):
```python
# tools/adsops/src/adsops/output.py
import sys
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message

def print_proto(msg: Message, fmt: str = "text") -> None:
    """Print proto message in requested format."""
    if fmt == "json":
        print(MessageToJson(msg))
    elif fmt == "proto":
        sys.stdout.buffer.write(msg.SerializeToString())
    else:
        print(proto_to_text(msg))  # rich table rendering

def print_protos(msgs: list[Message], fmt: str = "text") -> None:
    """Print a list of proto messages."""
    for msg in msgs:
        print_proto(msg, fmt)
```

**Error/logging pattern** (common.py lines 22-39 — reuse exactly):
```python
from scripts.python.common import log_info, log_success, log_warn, log_error
# OR copy the Colors class and log_* functions directly — they are 18 lines
```

---

### `tools/adsops/src/adsops/hostctl/models.py` (model, CRUD)

**Analog:** `tools/hostctl/types.go` (Resource struct, lines 8-27)

**Go Resource struct** (types.go lines 8-27):
```go
type Resource struct {
    ID                 int
    ResourceName       string
    Hostname           string
    Type               string
    Provider           string
    Region             sql.NullString   // nullable
    Status             string
    Environment        string
    Owners             []string         // ARRAY
    MailGroups         []string         // ARRAY — DB column: mailgroups (no underscore)
    Metadata           map[string]interface{}  // JSONB
    AverageDailyCost   sql.NullFloat64  // nullable
    AverageMonthlyCost sql.NullFloat64  // nullable
    ExternalID         sql.NullString   // nullable
    ExternalURL        sql.NullString   // nullable
    CreatedAt          time.Time
    UpdatedAt          time.Time
}
```

**SQLAlchemy model to write** (mirrors Go exactly per D-03):
```python
# tools/adsops/src/adsops/hostctl/models.py
from typing import Optional
import datetime
from sqlalchemy import Integer, String, Float, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, mapped_column

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
    # CRITICAL: DB column is "mailgroups" (no underscore) — Go uses mailgroups
    mail_groups: list[str] = mapped_column("mailgroups", ARRAY(String), nullable=False, default=list)
    metadata_: dict = mapped_column("metadata", JSONB, nullable=False, default=dict)
    average_daily_cost: Optional[float] = mapped_column(Float, nullable=True)
    average_monthly_cost: Optional[float] = mapped_column(Float, nullable=True)
    external_id: Optional[str] = mapped_column(String, nullable=True)
    external_url: Optional[str] = mapped_column(String, nullable=True)
    created_at: datetime.datetime = mapped_column(DateTime, nullable=False)
    updated_at: datetime.datetime = mapped_column(DateTime, nullable=False)
```

**Note:** `metadata` conflicts with SQLAlchemy's internal attribute — use `metadata_` as the Python attribute name, with `mapped_column("metadata", ...)` to map to the DB column.

---

### `tools/adsops/src/adsops/hostctl/db.py` (service, CRUD)

**Analog:** `tools/hostctl/database.go` (initDB/getDB, lines 17-63)

**Go connection pattern** (database.go lines 22-55 — env vars, connection string, ping):
```go
host := getEnvOrDefault("INVENTORY_DB_HOST", "afterdarksys.com")
port := getEnvOrDefault("INVENTORY_DB_PORT", "5432")
dbname := getEnvOrDefault("INVENTORY_DB_NAME", "inventory")
user := getEnvOrDefault("INVENTORY_DB_USER", "")
password := getEnvOrDefault("INVENTORY_DB_PASSWORD", "")
// ...
connStr := fmt.Sprintf("host=%s port=%s dbname=%s user=%s password=%s sslmode=require", ...)
db, err = sql.Open("postgres", connStr)
db.Ping()
db.SetMaxOpenConns(10)
```

**Python equivalent to write:**
```python
# tools/adsops/src/adsops/hostctl/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from adsops.config import get_db_url

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_db_url(),
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,  # equivalent to Ping()
        )
    return _engine

def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    factory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return factory()
```

---

### `tools/adsops/src/adsops/hostctl/service.py` (service, CRUD)

**Analog:** `tools/hostctl/database.go` (listResources/insertResource/updateResource, lines 74-598)

**list pattern** (database.go lines 464-543):
```go
// Dynamic WHERE clause with filter args
query := "SELECT ... FROM inventory_resources WHERE 1=1"
if opts.Status != "" { query += " AND status = $N"; args = append(args, opts.Status) }
// ...
rows, err := db.Query(query, args...)
for rows.Next() { scan → Resource }
```

**Python service pattern to write:**
```python
# tools/adsops/src/adsops/hostctl/service.py
from sqlalchemy import select
from adsops.hostctl.db import get_session
from adsops.hostctl.models import Resource
from adsops.v1 import host_pb2  # HostRecord proto

def list_resources(status=None, environment=None, type_=None, provider=None, region=None) -> list[host_pb2.HostRecord]:
    with get_session() as session:
        stmt = select(Resource)
        if status:
            stmt = stmt.where(Resource.status == status)
        if environment:
            stmt = stmt.where(Resource.environment == environment)
        # ... additional filters
        rows = session.scalars(stmt.order_by(Resource.hostname)).all()
        return [_to_proto(r) for r in rows]

def _to_proto(r: Resource) -> host_pb2.HostRecord:
    """Convert SQLAlchemy Resource ORM row to HostRecord proto (D-11)."""
    rec = host_pb2.HostRecord(
        id=r.id,
        resource_name=r.resource_name,
        hostname=r.hostname,
        type=r.type,
        provider=r.provider,
        status=r.status,
        environment=r.environment,
    )
    rec.owners.extend(r.owners or [])
    rec.mail_groups.extend(r.mail_groups or [])
    return rec
```

**Error handling pattern** (database.go line style — wrap with context):
```python
from sqlalchemy.exc import SQLAlchemyError

try:
    result = session.scalars(stmt).all()
except SQLAlchemyError as e:
    raise RuntimeError(f"failed to query resources: {e}") from e
```

---

### `tools/adsops/src/adsops/hostctl/cli.py` (cli-sub, request-response)

**Analog:** `tools/hostctl/commands.go` (runAdd/runList pattern, lines 1-80)

**Go command validation pattern** (commands.go lines 10-57 — validate then call DB):
```go
func runAdd(opts *AddOptions) error {
    if opts.Hostname == "" { return fmt.Errorf("hostname is required") }
    validTypes := []string{"server", "container", ...}
    if !contains(validTypes, opts.Type) { return fmt.Errorf("invalid type: %s ...", opts.Type) }
    resource, err := insertResource(opts)
    if jsonOutput { return printJSON(resource) }
    printSuccess(...)
    printResource(resource)
    return nil
}
```

**Typer CLI pattern to write** (from RESEARCH.md Pattern 4 + Go command surface):
```python
# tools/adsops/src/adsops/hostctl/cli.py
import typer
from typing import Annotated, Optional
from google.protobuf.json_format import MessageToJson

app = typer.Typer(help="Manage host inventory", no_args_is_help=True)

@app.command("list")
def list_hosts(
    status: Optional[str] = typer.Option(None, help="Filter by status"),
    environment: Optional[str] = typer.Option(None, "--env", help="Filter by environment"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
):
    from adsops.hostctl.service import list_resources
    from adsops.output import print_protos
    records = list_resources(status=status, environment=environment)
    fmt = "json" if json_out else ("proto" if proto_out else "text")
    print_protos(records, fmt)

@app.command("add")
def add_host(
    hostname: str = typer.Argument(..., help="Hostname to add"),
    # ... other options
    json_out: Annotated[bool, typer.Option("--json")] = False,
):
    from adsops.hostctl.service import add_resource
    from adsops.output import print_proto
    record = add_resource(hostname=hostname, ...)
    fmt = "json" if json_out else "text"
    print_proto(record, fmt)
```

---

### `tools/adsops/src/adsops/infractl/ssh.py` (service, request-response)

**Analog:** `tools/infractl/cmd/docker.go` (dockerRun/dockerStream, lines 214-235)

**Go SSH run pattern** (docker.go lines 214-235):
```go
func dockerRun(hostname, cmd string) error {
    ex, err := executorFor(hostname)
    out, err := ex.Run(context.Background(), cmd)
    fmt.Print(out)
    if err != nil && strings.TrimSpace(out) == "" {
        return fmt.Errorf("ssh: %w", err)
    }
    return nil
}

func dockerStream(hostname, cmd string) error {
    ex, err := executorFor(hostname)
    return ex.Stream(context.Background(), cmd, os.Stdout, os.Stderr)
}
```

**asyncssh Python equivalent to write** (D-04, D-05, D-06, D-07):
```python
# tools/adsops/src/adsops/infractl/ssh.py
import asyncio
import asyncssh
import os
import sys

async def run_command(host: str, command: str) -> tuple[str, str]:
    """Run command on remote host via SSH agent (D-05: agent only, no key files)."""
    if not os.environ.get("SSH_AUTH_SOCK"):
        raise RuntimeError("No SSH agent found. Run: eval $(ssh-agent) && ssh-add")
    async with asyncssh.connect(host, known_hosts=None) as conn:
        result = await conn.run(command, check=False)
        return result.stdout, result.stderr

async def stream_command(host: str, command: str) -> None:
    """Run command with streaming stdout (for logs -f, exec)."""
    async with asyncssh.connect(host, known_hosts=None) as conn:
        async with conn.create_process(command) as proc:
            async for line in proc.stdout:
                print(f"[{host}] {line}", end="")

async def run_parallel(hosts: list[str], command: str) -> list[tuple[str, str, str]]:
    """Run same command on multiple hosts via asyncio.gather() (D-07)."""
    async def _run(h):
        stdout, stderr = await run_command(h, command)
        return h, stdout, stderr
    return await asyncio.gather(*[_run(h) for h in hosts], return_exceptions=True)

def run_sync(host: str, command: str) -> tuple[str, str]:
    """Sync wrapper for use from Typer commands (D-06)."""
    return asyncio.run(run_command(host, command))

def run_parallel_sync(hosts: list[str], command: str) -> list[tuple[str, str, str]]:
    """Sync wrapper for multi-host execution (D-06 + D-07)."""
    return asyncio.run(run_parallel(hosts, command))
```

---

### `tools/adsops/src/adsops/infractl/docker.py` (service, request-response)

**Analog:** `tools/infractl/cmd/docker.go` (full file, lines 1-235)

**Command surface to replicate** (docker.go lines 34-211):
- `ls` → `docker ps --format '...'`
- `start <container...>` → `docker start {containers}`
- `stop <container...>` → `docker stop {containers}`
- `restart <container...>` → `docker restart {containers}`
- `logs <container>` → `docker logs [-f] [--tail N] [--since X] {container}` (streaming)
- `exec <container> [cmd]` → `docker exec [-it] {container} {cmd}` (streaming)

**Pattern to write:**
```python
# tools/adsops/src/adsops/infractl/docker.py
from adsops.infractl.ssh import run_sync, stream_command
import asyncio

def docker_ls(host: str, all_containers: bool = False) -> tuple[str, str]:
    flag = "-a " if all_containers else ""
    fmt = r"table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
    return run_sync(host, f"docker ps {flag}--format '{fmt}'")

def docker_start(host: str, containers: list[str]) -> tuple[str, str]:
    return run_sync(host, "docker start " + " ".join(containers))

def docker_stop(host: str, containers: list[str]) -> tuple[str, str]:
    return run_sync(host, "docker stop " + " ".join(containers))

def docker_restart(host: str, containers: list[str]) -> tuple[str, str]:
    return run_sync(host, "docker restart " + " ".join(containers))

def docker_logs(host: str, container: str, follow: bool = False, tail: str = "100") -> None:
    flags = f"--tail {tail}"
    if follow:
        flags += " -f"
    asyncio.run(stream_command(host, f"docker logs {flags} {container}"))

def docker_exec(host: str, container: str, cmd: str = "sh") -> None:
    asyncio.run(stream_command(host, f"docker exec {container} {cmd}"))
```

---

### `tools/adsops/src/adsops/infractl/k3s.py` (service, request-response)

**Analog:** `tools/infractl/cmd/k3s.go` (full file, lines 1-422)

**Command surface to replicate** (k3s.go lines 38-67 — kubectl helper + k3sRun/k3sStream):
```go
func kubectl(hostname, ns, subcmd string) error {
    nsFlag := ""
    if ns == "all" { nsFlag = "-A" } else if ns != "" { nsFlag = "-n " + ns }
    return k3sRun(hostname, "k3s kubectl "+subcmd+" "+nsFlag)
}
```

**k3s apply pattern** (k3s.go lines 357-379 — SCP then kubectl apply):
```go
remoteTmp := "/tmp/infractl-manifest-" + strings.ReplaceAll(localFile, "/", "_")
ex.ScpTo(ctx, localFile, remoteTmp)
k3sStream(hostname, "k3s kubectl apply -f " + remoteTmp + " && rm -f " + remoteTmp)
```

**Python pattern to write:**
```python
# tools/adsops/src/adsops/infractl/k3s.py
from adsops.infractl.ssh import run_sync, stream_command
import asyncio

def _kubectl(host: str, subcmd: str, ns: str = "") -> tuple[str, str]:
    ns_flag = "-A" if ns in ("all", "--all-namespaces") else (f"-n {ns}" if ns else "")
    return run_sync(host, f"k3s kubectl {subcmd} {ns_flag}".strip())

def k3s_nodes(host: str, wide: bool = False) -> tuple[str, str]:
    flags = "get nodes" + (" -o wide" if wide else "")
    return run_sync(host, f"k3s kubectl {flags}")

def k3s_pods(host: str, ns: str = "all", wide: bool = False) -> tuple[str, str]:
    return _kubectl(host, "get pods" + (" -o wide" if wide else ""), ns)

def k3s_logs(host: str, pod: str, ns: str = "", follow: bool = False, tail: str = "100") -> None:
    flags = f"logs {pod} --tail={tail}"
    if ns:
        flags += f" -n {ns}"
    if follow:
        flags += " -f"
    asyncio.run(stream_command(host, f"k3s kubectl {flags}"))

def k3s_apply(host: str, local_file: str, delete: bool = False) -> None:
    """SCP manifest to remote host and apply/delete it."""
    import asyncssh, asyncio, os
    remote_tmp = f"/tmp/adsops-manifest-{os.path.basename(local_file)}"
    verb = "delete" if delete else "apply"
    async def _apply():
        async with asyncssh.connect(host, known_hosts=None) as conn:
            await asyncssh.scp(local_file, (conn, remote_tmp))
            async with conn.create_process(f"k3s kubectl {verb} -f {remote_tmp} && rm -f {remote_tmp}") as proc:
                async for line in proc.stdout:
                    print(line, end="")
    asyncio.run(_apply())
```

---

### `tools/adsops/src/adsops/infractl/cli.py` (cli-sub, request-response)

**Analog:** `tools/infractl/cmd/docker.go` + `k3s.go` (command registration pattern)

**Nested sub-app pattern to write:**
```python
# tools/adsops/src/adsops/infractl/cli.py
import typer
from typing import Annotated, Optional

app = typer.Typer(help="Manage remote Docker and k3s infrastructure", no_args_is_help=True)
docker_app = typer.Typer(help="Docker commands over SSH", no_args_is_help=True)
k3s_app = typer.Typer(help="k3s/kubectl commands over SSH", no_args_is_help=True)
app.add_typer(docker_app, name="docker")
app.add_typer(k3s_app, name="k3s")

@docker_app.command("ls")
def docker_ls(
    host: str = typer.Argument(...),
    all_: Annotated[bool, typer.Option("--all", "-a")] = False,
):
    from adsops.infractl.docker import docker_ls as _ls
    stdout, stderr = _ls(host, all_containers=all_)
    if stdout: print(stdout)
    if stderr: print(stderr)

# ... similar pattern for start/stop/restart/logs/exec
# ... k3s_app commands follow same pattern calling adsops.infractl.k3s.*
```

---

### `tools/adsops/src/adsops/stats/local.py` (service, batch)

**Analog:** `tools/statsagent/collectors/docker.go` (DockerStats/ContainerStats struct, lines 13-35)

**Go stats struct** (docker.go lines 13-35 — field names map to proto):
```go
type ContainerStats struct {
    ID          string  `json:"id"`
    Name        string  `json:"name"`
    CPUPct      float64 `json:"cpu_pct"`
    MemUsedBytes int64  `json:"mem_used_bytes"`
    // ...
}
```

**Python psutil pattern to write** (D-11: output as StatsSnapshot proto):
```python
# tools/adsops/src/adsops/stats/local.py
import psutil
from google.protobuf.timestamp_pb2 import Timestamp
from adsops.v1 import stats_pb2  # StatsSnapshot proto
import datetime

def collect_once() -> stats_pb2.StatsSnapshot:
    """Collect local system metrics via psutil, return StatsSnapshot proto."""
    snap = stats_pb2.StatsSnapshot()
    ts = Timestamp()
    ts.FromDatetime(datetime.datetime.utcnow())
    snap.timestamp.CopyFrom(ts)

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # populate proto fields from psutil readings
    snap.cpu_percent = cpu
    snap.mem_used_bytes = mem.used
    snap.mem_total_bytes = mem.total
    snap.disk_used_bytes = disk.used
    snap.disk_total_bytes = disk.total

    return snap
```

---

### `tools/adsops/src/adsops/stats/remote.py` (service, request-response)

**Analog:** `scripts/python/test_central_auth.py` (_request method, lines 44-88)

**HTTP request pattern** (test_central_auth.py lines 44-88):
```python
def _request(self, method, endpoint, data=None, headers=None) -> dict:
    url = f"{self.base_url}{endpoint}"
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT, ...) as response:
            response_data = response.read().decode("utf-8")
            return json.loads(response_data)
    except urllib.error.HTTPError as e:
        raise AuthError(e.code, error_data.get("message", str(e)))
    except urllib.error.URLError as e:
        raise AuthError(0, f"Connection failed: {e.reason}")
```

**Async pattern to write** (use aiohttp per RESEARCH.md, wrapping with asyncio.run):
```python
# tools/adsops/src/adsops/stats/remote.py
import asyncio
import aiohttp
from google.protobuf.json_format import Parse
from adsops.v1 import telemetry_pb2

async def _fetch(host: str, port: int = 9100) -> telemetry_pb2.TelemetryPayload:
    url = f"http://{host}:{port}/stats"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            body = await resp.text()
            return Parse(body, telemetry_pb2.TelemetryPayload())

def fetch_once(host: str, port: int = 9100) -> telemetry_pb2.TelemetryPayload:
    """Sync wrapper for CLI use (D-06)."""
    return asyncio.run(_fetch(host, port))
```

---

### `tools/adsops/src/adsops/sysscript/mock.py` (utility, event-driven)

**No codebase analog.** Greenfield. Use RESEARCH.md Pattern 6 directly.

**Pattern to write** (from RESEARCH.md Pattern 6, extended to all 14 namespaces):
```python
# tools/adsops/src/adsops/sysscript/mock.py
from typing import Any, Callable

class MockNamespace:
    """Fixture-backed namespace that returns canned responses."""
    def __init__(self, name: str, fixtures: dict[str, Any]):
        self._name = name
        self._fixtures = fixtures

    def __getattr__(self, method: str) -> Callable:
        key = f"{self._name}.{method}"
        def _handler(*args, **kwargs):
            fixture = self._fixtures.get(key)
            if fixture is None:
                raise NotImplementedError(
                    f"MockSys: no fixture for '{key}'. "
                    f"Pass fixtures={{'{key}': <return_value>}} to MockSys()"
                )
            return fixture(*args, **kwargs) if callable(fixture) else fixture
        return _handler

class MockSys:
    """
    Drop-in replacement for the Starlark sys global.
    Tests pass fixture_data dict keyed by "namespace.method" and
    values are either return values or callables.

    Usage:
        sys = MockSys({"net.http_get": "OK", "exec.run": lambda cmd: (0, "output", "")})
    """
    def __init__(self, fixtures: dict[str, Any] | None = None):
        fixtures = fixtures or {}
        # All 14 namespaces from sysscript.go (verified) + k3s stub for Phase 3
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
        self.k3s = MockNamespace("k3s", fixtures)   # stub for Phase 3
```

---

### `tools/adsops/tests/conftest.py` (test config)

**Analog:** `scripts/python/test_central_auth.py` (class setup pattern, lines 27-89)

**Pattern to write** (pytest fixtures for DB session mock and asyncssh mock):
```python
# tools/adsops/tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_session():
    """Mocked SQLAlchemy session — avoids live DB for unit tests."""
    with patch("adsops.hostctl.db.get_session") as mock:
        session = MagicMock()
        mock.return_value.__enter__ = lambda s: session
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield session

@pytest.fixture
def mock_ssh():
    """Mocked asyncssh connection for infractl unit tests."""
    with patch("adsops.infractl.ssh.asyncssh.connect") as mock:
        conn = MagicMock()
        conn.__aenter__ = MagicMock(return_value=conn)
        conn.__aexit__ = MagicMock(return_value=False)
        mock.return_value = conn
        yield conn

@pytest.fixture
def mock_sys():
    """Pre-built MockSys instance with empty fixtures for test customization."""
    from adsops.sysscript.mock import MockSys
    return MockSys({})
```

---

### `tools/adsops/tests/test_*.py` (tests)

**Analog:** `scripts/python/test_central_auth.py` (test structure pattern)

**Error assertion pattern** (test_central_auth.py line style):
```python
# Error types always include code + message — mirror AuthError pattern:
class AdsopsError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)
```

**Test structure pattern for each test file:**
```python
# tools/adsops/tests/test_hostctl.py
import pytest
from unittest.mock import MagicMock

def test_list_resources_empty(mock_session):
    mock_session.scalars.return_value.all.return_value = []
    from adsops.hostctl.service import list_resources
    result = list_resources()
    assert result == []

def test_list_resources_with_filter(mock_session):
    # ... mock Resource ORM object, assert proto conversion
    pass
```

---

## Shared Patterns

### Env Var Loading (DB credentials)
**Source:** `tools/hostctl/database.go` lines 22-32; Python adaptation in `scripts/aftercloud/adsops_config.py` lines 140-143
**Apply to:** `tools/adsops/src/adsops/config.py`, `tools/adsops/src/adsops/hostctl/db.py`
```python
import os

def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"{key} environment variable is required")
    return val

INVENTORY_DB_HOST = os.environ.get("INVENTORY_DB_HOST", "afterdarksys.com")
INVENTORY_DB_PORT = os.environ.get("INVENTORY_DB_PORT", "5432")
INVENTORY_DB_NAME = os.environ.get("INVENTORY_DB_NAME", "inventory")
```

### Error Handling / Logging
**Source:** `scripts/python/common.py` lines 22-39
**Apply to:** All Python modules — copy or import Colors + log_* functions
```python
import sys

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def log_error(message: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}", file=sys.stderr)

def log_info(message: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")
```

### Proto Output Flags (--json / --proto)
**Source:** RESEARCH.md Pattern 5; Go analog `tools/hostctl/commands.go` lines 49-55 (jsonOutput flag)
**Apply to:** All `cli.py` sub-apps (hostctl, infractl, stats)
```python
from typing import Annotated
import typer

json_out: Annotated[bool, typer.Option("--json")] = False
proto_out: Annotated[bool, typer.Option("--proto")] = False
# Use sys.stdout.buffer.write() for --proto (never print())
```

### asyncio.run() Sync Wrapper (D-06)
**Source:** RESEARCH.md Pattern 3; Go analog: Cobra RunE functions call executor directly (synchronous)
**Apply to:** All `infractl/` commands and `stats/remote.py`
```python
import asyncio

def some_command_sync(*args) -> ...:
    """Typer commands are sync; wrap async core with asyncio.run()."""
    return asyncio.run(_some_command_async(*args))
```

### SSH Agent Guard
**Source:** RESEARCH.md Pitfall 3
**Apply to:** `tools/adsops/src/adsops/infractl/ssh.py` (checked once at connection time)
```python
import os

if not os.environ.get("SSH_AUTH_SOCK"):
    raise RuntimeError(
        "No SSH agent found. Run: eval $(ssh-agent) && ssh-add"
    )
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tools/adsops/src/adsops/sysscript/mock.py` | utility | event-driven | No test harness or mock namespace pattern exists in codebase — use RESEARCH.md Pattern 6 |
| `tools/adsops/src/adsops/hostctl/ssh_config.py` | utility | file-I/O | Go analog is `tools/infractl/ssh/config.go` (different language); stdlib has no SSH config parser — implement lightweight line reader per RESEARCH.md Open Question 1 |

---

## Metadata

**Analog search scope:** `scripts/python/`, `scripts/aftercloud/`, `tools/hostctl/`, `tools/infractl/cmd/`, `tools/statsagent/collectors/`, `gen/python/`, `opsctl.py`
**Files scanned:** 15 Python files, 5 Go reference files
**Pattern extraction date:** 2026-05-04
