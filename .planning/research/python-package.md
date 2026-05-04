# Python Package Research: adsops CLI

**Project:** tools/adsops — Python mirror of Go CLI toolkit
**Researched:** 2026-05-03
**Overall confidence:** HIGH (stack), MEDIUM (Starlark mock pattern), HIGH (packaging)

---

## 1. Typer vs Click for 2025

**Recommendation: Typer**

Typer is built on Click but adds type-hint-driven command definition. For a project mirroring a Go/Cobra CLI — where commands are organized into noun-verb subcommand trees — Typer's `add_typer()` pattern maps directly onto Cobra's `rootCmd.AddCommand()`.

**Why Typer wins here:**

- `app.add_typer(hosts_app, name="hosts")` mirrors `rootCmd.AddCommand(hostsCmd)` exactly
- Function signatures with type-annotated parameters replace manual `@click.option()` decoration — less boilerplate per command
- `typer.Typer(help="...")` on each sub-app gives clean `--help` output matching Go's usage strings
- Rich output (tables, progress) integrates naturally via `rich` library, which Typer already depends on
- Autocompletion works out of the box via type hints
- Current version: 0.12+ (Context7: 0.21.1)

**One gotcha (Typer >= 0.14.0):** Sub-app names are no longer inferred from callback function names. Always pass `name=` explicitly to `add_typer()`:

```python
app.add_typer(hosts_app, name="hosts")   # required, not inferred
app.add_typer(infra_app, name="infra")
app.add_typer(stats_app, name="stats")
```

**When Click is better:** When you need dynamic command loading at runtime (plugin systems), or when you're already deep in a Click codebase. Neither applies here.

**Confidence: HIGH** — verified against Context7 Typer docs (version 0.21.1).

---

## 2. pyproject.toml for src/ layout with entry points

Use `setuptools` as the build backend. The `src/` layout requires explicit package discovery scoped to `src/`.

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "adsops"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer[all]>=0.12",
    "paramiko>=3.4",
    "protobuf>=4.25",
    "rich>=13.0",
    "pyyaml>=6.0",
]

[project.scripts]
adsops = "adsops.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"
```

**Directory layout:**

```
tools/adsops/
  pyproject.toml
  src/
    adsops/
      __init__.py
      cli.py          # typer app, add_typer calls
      hosts/
        __init__.py
        commands.py   # mirrors hostctl commands.go
      infra/
        __init__.py
        commands.py   # mirrors infractl
      stats/
        __init__.py
        commands.py   # mirrors statsagent
      sys/
        __init__.py   # sys module interface
        mock.py       # test mock implementation
  tests/
    test_hosts.py
    test_infra.py
    test_sys_mock.py
```

**Editable install from repo root:**

```bash
pip install -e tools/adsops/
```

The `[project.scripts]` entry creates the `adsops` binary in the venv's `bin/`. Entry point changes (adding new scripts) require re-running `pip install -e .` — code changes do not.

**Protobuf bindings from gen/python/:**

Add the gen directory to the package path rather than copying generated files:

```toml
[tool.setuptools.packages.find]
where = ["src", "../../gen/python"]
```

Or use a `.pth` file, or set `PYTHONPATH=gen/python` in the dev environment. The cleanest approach for an internal tool is a `conftest.py` that adds `gen/python` to `sys.path`, and document that `PYTHONPATH` must include `gen/python` in shell profile or `.envrc`.

**Confidence: HIGH** — verified against Python Packaging User Guide and PEP 660.

---

## 3. SSH Command Execution: paramiko vs asyncssh vs subprocess

**Recommendation: paramiko for synchronous CLI commands; asyncssh if you need concurrent multi-host operations**

### paramiko (recommended default)

```python
import paramiko

def ssh_exec(host: str, command: str, timeout: int = 30) -> tuple[str, str, int]:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    try:
        client.connect(hostname=host, timeout=timeout)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        rc = stdout.channel.recv_exit_status()
        return out, err, rc
    finally:
        client.close()
```

**Pros:** Pure Python, no event loop required, respects `~/.ssh/config` and `~/.ssh/known_hosts`, widely deployed. Maps cleanly to how `infractl` uses `ssh/` package in Go. Version 3.4+ has good type annotations.

**Cons:** Blocking I/O — running commands on 20 hosts serially is slow.

### asyncssh (use when parallelism matters)

```python
import asyncio, asyncssh

async def ssh_exec_many(hosts: list[str], command: str):
    async def run_one(host):
        async with asyncssh.connect(host) as conn:
            result = await conn.run(command, check=True)
            return host, result.stdout, result.exit_status
    return await asyncio.gather(*[run_one(h) for h in hosts])
```

**Pros:** Native async, excellent for fan-out (deploy to N hosts). `conn.run()` API is cleaner than paramiko's channel-level API.

**Cons:** Requires async context throughout. If the CLI is sync (Typer default), you'll call `asyncio.run()` at the boundary, which is fine but adds a layer.

### subprocess + system ssh (avoid)

Spawning `ssh` subprocesses works but loses structured error handling, requires parsing stderr, and can't reuse connections. Only use this if you need ProxyJump chains that paramiko handles poorly.

**Decision for adsops:** Start with paramiko. If `infra` commands need parallel deployment (like `infractl deploy --all`), wrap that command with asyncssh behind a thin `asyncio.run()` call.

**Confidence: HIGH** — verified against Context7 paramiko and asyncssh docs.

---

## 4. Python Mock for Starlark sys Module

There is no off-the-shelf Python mock for a custom Starlark `sys` module. The pattern to use is `python-starlark-go` (PyPI: `starlark-go`) to execute `.star` files from Python, combined with a pure-Python dict/object that you inject as the `sys` predeclared name.

**Architecture:**

The Starlark interpreter (via `starlark-go` Python bindings) accepts a `predeclared` dict when evaluating a script. Inject a Python object whose attributes mirror your `sys.*` interface:

```python
# src/adsops/sys/mock.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class MockFs:
    files: dict[str, str] = field(default_factory=dict)

    def read(self, path: str) -> str:
        return self.files.get(path, "")

    def write(self, path: str, content: str) -> None:
        self.files[path] = content

    def exists(self, path: str) -> bool:
        return path in self.files

@dataclass
class MockExec:
    calls: list[tuple[str, list[str]]] = field(default_factory=list)
    responses: dict[str, str] = field(default_factory=dict)

    def run(self, cmd: str, *args) -> str:
        self.calls.append((cmd, list(args)))
        return self.responses.get(cmd, "")

@dataclass
class MockNet:
    responses: dict[str, Any] = field(default_factory=dict)

    def get(self, url: str) -> Any:
        return self.responses.get(url, {})

@dataclass
class MockContainers:
    running: list[str] = field(default_factory=list)

    def list(self) -> list[str]:
        return self.running

@dataclass
class MockSys:
    fs: MockFs = field(default_factory=MockFs)
    exec: MockExec = field(default_factory=MockExec)
    net: MockNet = field(default_factory=MockNet)
    containers: MockContainers = field(default_factory=MockContainers)
    k3s: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    yaml: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)
```

**Test harness using python-starlark-go:**

```python
# tests/test_sys_mock.py
import starlark  # python-starlark-go
from adsops.sys.mock import MockSys

def run_star(script: str, sys_mock: MockSys | None = None) -> dict:
    if sys_mock is None:
        sys_mock = MockSys()
    # python-starlark-go exposes ExecFile / Eval with predeclared dict
    thread = starlark.Thread(name="test")
    predeclared = {"sys": sys_mock}
    return starlark.exec_file(thread, "<test>", script, predeclared)

def test_fs_read():
    mock = MockSys()
    mock.fs.files["/etc/hosts"] = "127.0.0.1 localhost"
    run_star('content = sys.fs.read("/etc/hosts")', mock)
```

**Caveat:** `python-starlark-go` (PyPI) wraps the Go starlark-go implementation via CGo. It works but requires Go toolchain at build time. If that's undesirable, `starlark-python` (pure Python Starlark interpreter, less maintained) is an alternative. For internal tooling where Go is already present, `python-starlark-go` is the right call.

**The mock objects themselves don't depend on any Starlark library** — they're just Python dataclasses. You can unit-test the mock logic independently, and the Starlark execution layer is a thin integration test.

**Confidence: MEDIUM** — `python-starlark-go` approach verified via PyPI/docs. Mock injection pattern is standard; specific `predeclared` API surface confirmed from starlark-go docs.

---

## 5. Type Stubs for Protobuf-Generated Python

**Recommendation: mypy-protobuf to generate `.pyi` stubs at codegen time**

Run `protoc` with the `mypy-protobuf` plugin to emit `.pyi` stub files alongside the generated `_pb2.py` files:

```bash
pip install mypy-protobuf
protoc \
  --python_out=gen/python \
  --mypy_out=gen/python \
  proto/adsops/v1/*.proto
```

This emits `*_pb2.pyi` next to each `*_pb2.py`. Both mypy and pyright pick these up automatically — no extra configuration needed.

**Also install:**

```toml
# pyproject.toml dev dependencies
[project.optional-dependencies]
dev = [
    "mypy>=1.10",
    "mypy-protobuf>=3.6",
    "types-protobuf>=4.25",
    "grpc-stubs>=1.53",  # if using grpc
]
```

**pyright note:** `mypy-protobuf` 3.6+ includes suppression of `reportSelfClsParameterName` warnings that pyright raises on proto-generated `self` field names. Pyright 1.1.408+ is fully compatible.

**Workflow:** Add `--mypy_out=gen/python` to your `Makefile` protoc invocation. Commit the `.pyi` files to the repo alongside the `_pb2.py` files. This means type checking works without running protoc locally.

**Confidence: HIGH** — verified against mypy-protobuf PyPI, types-protobuf PyPI, and GitHub nipunn1313/mypy-protobuf.

---

## 6. Package Structure: Library API + CLI Entry Points

**Pattern: thin CLI layer over importable library core**

```
src/adsops/
  __init__.py          # public API exports
  cli.py               # typer app — ONLY wires commands, no business logic
  hosts/
    __init__.py
    api.py             # HostDB, HostRecord — importable library
    commands.py        # typer commands that call api.py
  infra/
    __init__.py
    api.py             # SSH execution, Docker/k3s operations
    commands.py
  stats/
    __init__.py
    api.py             # metrics collection
    commands.py
  sys/
    __init__.py        # SysInterface protocol/ABC
    mock.py            # MockSys for testing
    live.py            # LiveSys — real implementation
```

**cli.py is a pure wiring file:**

```python
# src/adsops/cli.py
import typer
from adsops.hosts.commands import app as hosts_app
from adsops.infra.commands import app as infra_app
from adsops.stats.commands import app as stats_app

app = typer.Typer(name="adsops", help="AdsOps infrastructure utilities")
app.add_typer(hosts_app, name="hosts")
app.add_typer(infra_app, name="infra")
app.add_typer(stats_app, name="stats")

if __name__ == "__main__":
    app()
```

**Why this matters:**
- `api.py` modules are importable from other internal tools or scripts without the CLI layer
- Tests import `api.py` directly — no subprocess needed for unit tests
- CLI commands stay thin: parse args, call api, format output
- Mirrors how Go separates `cmd/` (cobra wiring) from `internal/` (business logic) and `pkg/` (public API)

**For the `sys` interface, define a Protocol:**

```python
# src/adsops/sys/__init__.py
from typing import Protocol

class FsInterface(Protocol):
    def read(self, path: str) -> str: ...
    def write(self, path: str, content: str) -> None: ...
    def exists(self, path: str) -> bool: ...

class SysInterface(Protocol):
    fs: FsInterface
    # ... etc
```

Both `MockSys` and `LiveSys` satisfy the Protocol. Functions that need `sys` take `sys: SysInterface` — fully type-checkable, no ABC inheritance required.

**Confidence: HIGH** — standard Python packaging pattern, well established.

---

## Summary Recommendations

| Question | Answer | Confidence |
|---|---|---|
| Typer vs Click | Typer — `add_typer()` maps to Cobra `AddCommand()` | HIGH |
| pyproject.toml layout | setuptools + src/ + `[project.scripts]` | HIGH |
| SSH execution | paramiko sync; asyncssh if fan-out needed | HIGH |
| Starlark mock | python-starlark-go + Python dataclass MockSys | MEDIUM |
| Protobuf type stubs | mypy-protobuf `--mypy_out`, commit `.pyi` files | HIGH |
| Library+CLI structure | api.py / commands.py split, Protocol for sys | HIGH |

## Key Dependencies

```toml
# runtime
typer[all]>=0.12
paramiko>=3.4
protobuf>=4.25
rich>=13.0
pyyaml>=6.0

# dev/test
mypy>=1.10
mypy-protobuf>=3.6
types-protobuf>=4.25
pytest>=8.0
starlark-go>=1.1   # for .star test harness (requires Go toolchain)
```

## Sources

- [Typer docs — subcommands/add_typer](https://github.com/fastapi/typer/blob/master/docs/tutorial/subcommands/callback-override.md)
- [Click docs — command groups](https://github.com/pallets/click/blob/main/docs/commands-and-groups.md)
- [Python Packaging User Guide — pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [PEP 660 — Editable installs](https://peps.python.org/pep-0660/)
- [paramiko docs — exec_command](https://context7.com/paramiko/paramiko/llms.txt)
- [asyncssh docs — conn.run()](https://context7.com/ronf/asyncssh/llms.txt)
- [mypy-protobuf PyPI](https://pypi.org/project/mypy-protobuf/)
- [types-protobuf PyPI](https://pypi.org/project/types-protobuf/)
- [python-starlark-go PyPI](https://pypi.org/project/starlark-go/)
