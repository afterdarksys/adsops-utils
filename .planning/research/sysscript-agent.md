# Research: systemapi-agent + sysscript ecosystem

**Researched:** 2026-05-03
**Confidence:** HIGH (go.starlark.net via Context7; Docker socket pattern from existing codebase)

---

## Topic 1: Docker socket integration for Starlark builtins

### 1.1 Best Go library: raw HTTP over Unix socket (no docker/docker SDK)

**Recommendation: keep the pattern already in `tools/statsagent/collectors/docker.go`.**

The existing codebase already proves the approach: a custom `dockerClient` that dials
`/var/run/docker.sock` via `net/http` Transport with a `DialContext` override. This is
preferable to pulling in `github.com/docker/docker` (the moby client) for several reasons:

- docker/docker is a large dependency tree (100+ transitive deps, ~30 MB compiled)
- The Engine API is stable JSON-over-HTTP; a thin client is all that is needed
- `stream=false` on `/containers/{id}/stats` returns a single sample with no goroutine
  lifecycle to manage
- The statsagent pattern already handles CPU%, mem, network delta — reuse it

The `moby/moby` client is appropriate when you need image build, volume management, or
event streaming. For read-only ops (list, inspect, stats) the raw socket approach is
strictly better.

### 1.2 Implementing sys.containers.list()

Wire up a `starlark.NewBuiltin` that calls `/containers/json?all=true`, unmarshals the
array, and builds a `starlark.List` of `*starlark.Dict` values. The field set to expose:

```go
// containerToStarlark converts a dockerContainer into a Starlark dict.
func containerToStarlark(c dockerContainer) *starlark.Dict {
    d := new(starlark.Dict)
    d.SetKey(starlark.String("id"),    starlark.String(c.ID[:12]))
    d.SetKey(starlark.String("name"),  starlark.String(stripLeadingSlash(c.Names)))
    d.SetKey(starlark.String("image"), starlark.String(c.Image))
    d.SetKey(starlark.String("state"), starlark.String(c.State))
    return d
}

// Builtin: sys.containers.list()
func starContainersList(dc *dockerClient) starlark.Value {
    return starlark.NewBuiltin("list", func(
        thread *starlark.Thread,
        b *starlark.Builtin,
        args starlark.Tuple,
        kwargs []starlark.Tuple,
    ) (starlark.Value, error) {
        if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 0); err != nil {
            return nil, err
        }
        data, err := dc.get("/containers/json?all=true")
        if err != nil {
            return starlark.None, nil // Docker unavailable — return None, not error
        }
        var containers []dockerContainer
        if err := json.Unmarshal(data, &containers); err != nil {
            return nil, fmt.Errorf("containers.list: %w", err)
        }
        elems := make([]starlark.Value, len(containers))
        for i, c := range containers {
            elems[i] = containerToStarlark(c)
        }
        return starlark.NewList(elems), nil
    })
}
```

Returning `starlark.None` (not an error) when Docker is unavailable matches the statsagent
convention and lets scripts handle the absence gracefully:

```python
containers = sys.containers.list()
if containers == None:
    print("docker not available")
```

### 1.3 Implementing sys.containers.stats(id) — single-sample

The Docker stats endpoint with `?stream=false` returns one JSON blob immediately; no
goroutine needed. The statsagent already has `enrichContainerStats` which does the CPU%
delta math. For the Starlark builtin, skip the delta (first call has no previous sample)
and return raw values — scripts that care about rate can call twice and do the math, or
the agent can maintain a per-container previous-sample cache like statsagent does.

```go
// Builtin: sys.containers.stats(id)
func starContainersStats(dc *dockerClient) starlark.Value {
    return starlark.NewBuiltin("stats", func(
        thread *starlark.Thread,
        b *starlark.Builtin,
        args starlark.Tuple,
        kwargs []starlark.Tuple,
    ) (starlark.Value, error) {
        var id string
        if err := starlark.UnpackPositionalArgs(b.Name(), args, kwargs, 1, &id); err != nil {
            return nil, err
        }
        data, err := dc.get("/containers/" + id + "/stats?stream=false")
        if err != nil {
            return starlark.None, nil
        }
        var r dockerStatsResponse
        if err := json.Unmarshal(data, &r); err != nil {
            return nil, fmt.Errorf("containers.stats: %w", err)
        }
        d := new(starlark.Dict)
        d.SetKey(starlark.String("cpu_pct"),        starlark.Float(calcCPU(r)))
        d.SetKey(starlark.String("mem_used_bytes"), starlark.MakeInt64(r.MemoryStats.Usage-r.MemoryStats.Stats.Cache))
        d.SetKey(starlark.String("mem_limit_bytes"),starlark.MakeInt64(r.MemoryStats.Limit))
        return d, nil
    })
}
```

Reuse `dockerStatsResponse` and `enrichContainerStats` from the statsagent package by
moving them to an internal/docker package, or copy the minimal structs into the agent.

### 1.4 Namespace wiring: sys.containers as a starlarkstruct.Module

Use `starlarkstruct.Module` (from `go.starlark.net/starlarkstruct`) to expose sub-namespaces.
This is the canonical pattern for `sys.x.y()` style APIs:

```go
import "go.starlark.net/starlarkstruct"

func buildSysModule(dc *dockerClient) *starlarkstruct.Module {
    return &starlarkstruct.Module{
        Name: "sys",
        Members: starlark.StringDict{
            "containers": &starlarkstruct.Module{
                Name: "containers",
                Members: starlark.StringDict{
                    "list":  starContainersList(dc),
                    "stats": starContainersStats(dc),
                    "run":   starContainersRun(dc), // existing stub
                },
            },
            // future: "k3s", "net", "exec"
        },
    }
}

// Wire into predeclared:
predeclared := starlark.StringDict{
    "sys": buildSysModule(dc),
}
```

`starlarkstruct.Module` is immutable and attribute-accessed via `.` in Starlark, so
`sys.containers.list()` works exactly as expected.

### 1.5 Security: entitlement checking pattern for containers

The billing `entitlement` system is CLI-level (user tokens, HTTP API). For the agent the
correct security layer is **capability gating at builtin registration time**, not per-call:

```go
// AgentConfig carries what this agent instance is allowed to do.
type AgentConfig struct {
    AllowDocker bool
    AllowK3s    bool
    AllowExec   bool
    SocketPath  string
}

func buildSysModule(cfg AgentConfig) *starlarkstruct.Module {
    members := starlark.StringDict{}

    if cfg.AllowDocker {
        dc := newDockerClient(cfg.SocketPath)
        members["containers"] = &starlarkstruct.Module{
            Name:    "containers",
            Members: starlark.StringDict{
                "list":  starContainersList(dc),
                "stats": starContainersStats(dc),
                "run":   starContainersRun(dc),
            },
        }
    }
    // sys.containers is simply absent if AllowDocker == false.
    // Scripts that try sys.containers.list() get AttributeError.
    return &starlarkstruct.Module{Name: "sys", Members: members}
}
```

This is preferable to a runtime permission check because:
- AttributeError is deterministic and caught during script development
- No runtime permission state to synchronize
- The same script run on a stripped-down agent fails loudly at load, not silently

For scripts that need to probe capability at runtime, add a `sys.has(feature_name)`
builtin that returns a bool — this is more explicit than `hasattr(sys, "containers")`.

---

## Topic 2: Starlark sysscript library patterns

### 2.1 load() in Starlark — yes it works, requires Thread.Load callback

The `load()` statement IS supported by go.starlark.net but **it is not enabled by
default**. The interpreter only executes `load()` if `thread.Load` is set. If `Load` is
nil, any `load()` call raises an error at runtime.

Syntax:
```python
load("lib/health.star", "check_http", "check_port")
load("lib/health.star", http_check="check_http")   # rename on import
```

Rules:
- At least two arguments: module path + one or more name bindings
- The module path is an opaque string passed verbatim to `Thread.Load`
- The returned `starlark.StringDict` is the module's top-level bindings

### 2.2 How go.starlark.net handles load() — file-based loading via Thread.Load

The `Thread.Load` field has type `func(thread *Thread, module string) (StringDict, error)`.
The runtime calls this function with the module path string from the `load()` call. The
host Go program is fully responsible for resolution — there is no default file resolver.

**Canonical file-based loader with caching and cycle detection** (from go.starlark.net
official example, confirmed via Context7):

```go
type ScriptLoader struct {
    BaseDir string
    cache   map[string]starlark.StringDict
    mu      sync.Mutex
    predeclared starlark.StringDict
}

func (l *ScriptLoader) Load(thread *starlark.Thread, module string) (starlark.StringDict, error) {
    l.mu.Lock()
    if globals, ok := l.cache[module]; ok {
        l.mu.Unlock()
        return globals, nil
    }
    // nil sentinel = "currently loading" (cycle detection)
    l.cache[module] = nil
    l.mu.Unlock()

    path := filepath.Join(l.BaseDir, module)
    src, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("load %q: %w", module, err)
    }

    modThread := &starlark.Thread{
        Name: "load:" + module,
        Load: l.Load, // allow transitive loads
    }
    globals, err := starlark.ExecFile(modThread, path, src, l.predeclared)
    if err != nil {
        return nil, err
    }

    l.mu.Lock()
    l.cache[module] = globals
    l.mu.Unlock()
    return globals, nil
}
```

Key points:
- `nil` sentinel in cache during execution detects cycles (returns "cycle in load graph" error)
- Transitive loads work because `modThread.Load` is set to the same `Load` func
- `predeclared` must be passed to `ExecFile` so lib scripts can also use `sys.*`
- The loader is stateful — one `ScriptLoader` per agent execution session, not per script

### 2.3 Best pattern for sysscripts/lib/ shared library

**Recommended layout:**

```
sysscripts/
  lib/
    health.star      # http + tcp health check helpers
    fmt.star         # formatting helpers (bytes, duration, etc.)
    k8s.star         # k3s / kubernetes helpers (future)
  services/
    nginx.star       # nginx-specific health/stats
    postgres.star    # postgres-specific checks
  host/
    base.star        # host-level stats (cpu, mem, disk)
```

**ScriptLoader configuration** — set `BaseDir` to the sysscripts root so that:
```python
load("lib/health.star", "http_ok")    # resolves to sysscripts/lib/health.star
load("lib/fmt.star", "human_bytes")   # resolves to sysscripts/lib/fmt.star
```

Absolute paths (`/etc/systemapi/sysscripts/lib/health.star`) work but are fragile across
deployments. Relative paths from a configured base are better.

**Alternative: virtual module loader** — register well-known modules by name rather than
path, so library scripts use `load("@health", "http_ok")` with an `@`-prefix convention.
The loader checks for `@` prefix first and serves from an embedded Go map, then falls
through to file resolution. This allows the agent to ship built-in libraries that can't
be tampered with on-disk while still allowing custom scripts.

```go
func (l *ScriptLoader) Load(thread *starlark.Thread, module string) (starlark.StringDict, error) {
    if strings.HasPrefix(module, "@") {
        return l.loadBuiltinModule(module[1:]) // served from embed.FS
    }
    return l.loadFileModule(module)
}
```

### 2.4 Example health check .star script pattern

```python
# sysscripts/services/nginx.star
load("lib/health.star", "http_ok", "tcp_open")

def health():
    results = {}

    # HTTP check
    r = sys.net.http_get("http://localhost/nginx_status", timeout=3)
    if r == None:
        results["http"] = {"ok": False, "reason": "unreachable"}
    else:
        results["http"] = {
            "ok": r["status"] == 200,
            "status": r["status"],
        }

    # Process check
    out = sys.exec.run(["pgrep", "-c", "nginx"])
    results["process"] = {
        "ok": out["exit_code"] == 0,
        "count": int(out["stdout"].strip()) if out["exit_code"] == 0 else 0,
    }

    return results

def stats():
    r = sys.net.http_get("http://localhost/nginx_status")
    if r == None:
        return {}

    # nginx_status body: "Active connections: 42\n..."
    lines = r["body"].split("\n")
    active = 0
    for line in lines:
        if line.startswith("Active connections:"):
            active = int(line.split(":")[1].strip())

    return {"active_connections": active}
```

**lib/health.star** — reusable helpers:

```python
# sysscripts/lib/health.star

def http_ok(url, timeout=5, expected_status=200):
    """Returns True if url responds with expected_status."""
    r = sys.net.http_get(url, timeout=timeout)
    if r == None:
        return False
    return r["status"] == expected_status

def tcp_open(host, port, timeout=3):
    """Returns True if TCP connection to host:port succeeds."""
    r = sys.net.tcp_connect(host, port, timeout=timeout)
    return r != None and r["ok"]

def check_or_fail(name, fn):
    """Runs fn(), returns {"name": name, "ok": bool, "error": str}."""
    result = fn()
    if type(result) == "bool":
        return {"name": name, "ok": result, "error": ""}
    return {"name": name, "ok": result.get("ok", False), "error": result.get("reason", "")}
```

**Agent-side execution pattern** — how the agent runs a service's health script:

```go
func (a *Agent) RunScript(scriptPath string) (starlark.StringDict, error) {
    loader := &ScriptLoader{
        BaseDir:     a.cfg.SysscriptDir,
        cache:       make(map[string]starlark.StringDict),
        predeclared: a.predeclared, // contains "sys" module
    }

    thread := &starlark.Thread{
        Name:  filepath.Base(scriptPath),
        Load:  loader.Load,
        Print: func(_ *starlark.Thread, msg string) { a.log.Info(msg) },
    }

    src, err := os.ReadFile(scriptPath)
    if err != nil {
        return nil, err
    }

    globals, err := starlark.ExecFile(thread, scriptPath, src, a.predeclared)
    if err != nil {
        return nil, err
    }

    // Callers invoke globals["health"] or globals["stats"] as Starlark callables
    return globals, nil
}
```

---

## Key decisions summary

| Decision | Recommendation | Rationale |
|---|---|---|
| Docker client library | Raw HTTP over Unix socket (copy statsagent pattern) | Zero extra deps, already proven in codebase |
| Docker SDK (docker/docker) | Do not use | 100+ deps, unnecessary for read-only ops |
| sys.* namespace type | `starlarkstruct.Module` | Immutable, attribute-access works, canonical pattern |
| Security model | Capability gating at module construction | Fail-fast, no runtime state, clear errors |
| load() loader | `Thread.Load` func with BaseDir + cache | Official go.starlark.net pattern, handles cycles |
| Library resolution | Relative paths from configured BaseDir | Portable across deployments |
| Built-in libs | `@`-prefix virtual modules from embed.FS | Tamper-proof standard library |
| stats single-sample | `/stats?stream=false` | Returns immediately, no streaming goroutine |
| Container stats delta | Skip for first call, return raw | Scripts that need rate do two calls |

## Dependencies to add to go.mod

```
go.starlark.net v0.0.0-20240520160348-046347dcd104  # or latest
```

`go.starlark.net/starlarkstruct` is part of the same module — no separate import needed.

## Sources

- go.starlark.net Thread.Load pattern: Context7 /google/starlark-go (HIGH confidence)
- go.starlark.net NewBuiltin/starlarkstruct.Module: Context7 /google/starlark-go (HIGH confidence)
- Docker socket HTTP pattern: `tools/statsagent/collectors/docker.go` in this repo (HIGH confidence)
- Docker API `?stream=false` single-sample: verified in statsagent codebase + Docker Engine API docs (HIGH confidence)
