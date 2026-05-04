# Phase 3: systemapi-agent Improvements - Research

**Researched:** 2026-05-04
**Domain:** Go / Starlark runtime extensions — Docker Unix socket API, Kubernetes REST API, go.starlark.net Thread.Load, proto import via go.mod replace
**Confidence:** HIGH

---

## Summary

Phase 3 extends the existing `systemapi-agent` Go binary (at `/Users/ryan/development/systemapi.io/systemapi-agent`) with three major capabilities: a real `sys.containers` Starlark module backed by raw Docker Engine API calls over the Unix socket, a new `sys.k3s` module backed by raw Kubernetes REST API calls with TLS from kubeconfig, and a wired `Thread.Load` callback that resolves `load()` paths relative to `/etc/systemapi/scripts/`. Every 5-second telemetry push is extended to include Docker container stats and k3s cluster state, aligned to the proto-generated `DockerStats` and `K3SStats` types already present in `adsops-utils/gen/go/`.

The codebase is a single Go package (`package main`), all files flat in the repo root. The Starlark builtins follow a uniform pattern (`func (engine *SysscriptEngine) methodName(thread, b, args, kwargs)` + `starlark.UnpackArgs` + `starlark.None, fmt.Errorf` for errors). The existing `buildSysModule()` function assembles all sub-modules into `sysDict` and then wraps them with `starlarkstruct.FromStringDict` — the entitlement-conditional include pattern is the correct approach for containers/k3s (per D-11), NOT the `if !AllowExec { return error }` inline guard.

The proto bindings (`gen/go/adsops/v1/`) are already generated and committed in `adsops-utils`. The `TelemetryPayload` proto struct has `Docker *DockerStats` (field 9) and `K3S *K3SStats` (field 10) already defined. The agent's local `TelemetryPayload` struct needs to be replaced or augmented to use these types. The module import path is `github.com/afterdarksys/adsops-utils/gen/go` and the `gen/go/` directory already has its own `go.mod`.

**Primary recommendation:** Create three new Go source files in the agent repo — `sys_containers.go`, `sys_k3s.go`, and `docker_client.go`/`k3s_client.go` — using raw HTTP over the Docker Unix socket and raw HTTPS with TLS from kubeconfig for k3s, following the existing builtin method pattern throughout.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Read `DOCKER_HOST` env var if set; fall back to `/var/run/docker.sock`.
- **D-02:** On socket unavailable or request failure, `sys.containers.list()` (and all container methods) return an empty list and log the error. Non-fatal.
- **D-03:** Use raw HTTP over Unix socket (`http.Transport` with `net.Dial("unix", socketPath)`) — no moby/docker SDK.
- **D-04:** Try `/etc/rancher/k3s/k3s.yaml` first, then fall back to `KUBECONFIG` env var.
- **D-05:** On k3s unavailable, `sys.k3s.nodes()` and `sys.k3s.pods()` return empty list and log the error. Non-fatal.
- **D-06:** `sys.k3s.apply(yaml_str)` is in scope for Phase 3. Implement as raw HTTP PATCH/POST to the Kubernetes API.
- **D-07:** `load("lib/helper.star", "fn")` resolves relative to `/etc/systemapi/scripts/`.
- **D-08:** `Thread.Load` is set on the `starlark.Thread` in `SysscriptEngine.Execute()` before `starlark.ExecFile`.
- **D-09:** If a load() target doesn't exist, `Thread.Load` returns an error — script fails fast.
- **D-10:** Add `AllowContainers bool` and `AllowK3s bool` fields to the `Entitlements` struct.
- **D-11:** Enforcement in `buildSysModule()`: if `!AllowContainers`, the `"containers"` key is NOT added to `sysDict`. Same for `"k3s"` and `AllowK3s`.
- **D-12:** Proto bindings from `adsops-utils/gen/go/adsops/v1/` imported via `go.mod replace`. `TelemetryPayload` extended with `Docker []ContainerStats` and `K3s K3sStats` fields aligned to proto definitions.

### Claude's Discretion

- Docker API version to target (use `v1.41` or negotiate via API version negotiation endpoint)
- k8s API client implementation details (raw HTTP with TLS from kubeconfig, no k8s client-go dependency unless needed)
- JSON struct tags and exact field naming for telemetry additions
- Error logging verbosity and format (use existing `log.Printf` pattern)
- Whether to cache Docker/k3s data between telemetry ticks or re-query every 5s

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGENT-01 | `sys.containers.list()` — returns all containers via Docker Unix socket | Docker Engine API GET /containers/json over Unix socket with raw HTTP transport |
| AGENT-02 | `sys.containers.stats(id)` — returns CPU/mem/net for a container | Docker Engine API GET /containers/{id}/stats?stream=false; CPU delta formula documented |
| AGENT-03 | `sys.containers.stop(id)`, `sys.containers.start(id)`, `sys.containers.restart(id)` | Docker Engine API POST /containers/{id}/stop|start|restart |
| AGENT-04 | New `sys.k3s` Starlark module: `nodes()`, `pods(namespace)`, `apply(yaml_str)` | Kubernetes REST API /api/v1/nodes, /api/v1/pods, raw HTTP with TLS from kubeconfig |
| AGENT-05 | `TelemetryPayload` extended with `docker` and `k3s` fields (every 5s push) | Proto structs `DockerStats` and `K3SStats` already generated; local struct needs update |
| AGENT-06 | Telemetry struct types aligned with proto definitions in adsops-utils | `go.mod replace` directive against `github.com/afterdarksys/adsops-utils/gen/go` |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| sys.containers.* Starlark builtins | Agent (Go) | — | Starlark runtime lives entirely in the agent binary |
| Docker socket I/O | Agent (Go) | — | Unix socket is local to the host the agent runs on |
| sys.k3s.* Starlark builtins | Agent (Go) | — | Same as containers — all in the agent binary |
| k3s API TLS client | Agent (Go) | — | Reads kubeconfig from local filesystem |
| Thread.Load / script loading | Agent (Go) | — | Set on `starlark.Thread` in Execute(), resolved from /etc/systemapi/scripts/ |
| TelemetryPayload extension | Agent (Go) | — | gatherTelemetry() in telemetry.go; pushed over existing WebSocket |
| Proto type alignment | Proto (adsops-utils gen/) | Agent import | agent imports via go.mod replace directive |
| Entitlement enforcement | Agent (Go) | — | buildSysModule() conditionally adds/omits keys from sysDict |

---

## Standard Stack

### Core (already in go.mod — no new deps required for most features)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `go.starlark.net` | v0.0.0-20260210143700-b62fd896b91b | Starlark interpreter, Thread.Load | Already in go.mod; provides Thread.Load callback |
| `go.starlark.net/starlarkstruct` | (same module) | `starlarkstruct.FromStringDict` for module assembly | Already used in buildSysModule() |
| `net/http` + `net` stdlib | Go stdlib | Raw HTTP over Unix socket; TLS HTTP client for k3s | No new dep; matches D-03 and D-06 |
| `crypto/tls` + `crypto/x509` | Go stdlib | Build TLS config from kubeconfig CA/client certs | No new dep; k8s uses mTLS |
| `encoding/json` | Go stdlib | Parse Docker API and k8s API JSON responses | Already used throughout codebase |
| `gopkg.in/yaml.v3` | v3.0.1 | Parse kubeconfig YAML | Already in go.mod |

### New Dependency (proto import)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `github.com/afterdarksys/adsops-utils/gen/go` | local (replace) | DockerStats, K3SStats, TelemetryPayload proto types | AGENT-06 alignment; added via `go.mod replace` |
| `google.golang.org/protobuf` | v1.34.1 (from gen/go/go.sum) | proto runtime (transitive from gen/go) | Required by generated proto bindings |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw HTTP over Unix socket | `github.com/docker/docker/client` (moby SDK) | Explicitly rejected by D-03 and success criteria #1 |
| Raw HTTP + yaml kubeconfig | `k8s.io/client-go` | Adds large transitive dependency tree; not needed for read-only API calls |
| `gopkg.in/yaml.v3` for kubeconfig | Custom parser | Already in go.mod; kubeconfig is standard YAML |

**Installation (proto replace directive):**
```bash
# In systemapi-agent go.mod, add:
require github.com/afterdarksys/adsops-utils/gen/go v0.0.0
replace github.com/afterdarksys/adsops-utils/gen/go => /Users/ryan/development/adsops-utils/gen/go

# Then:
cd /Users/ryan/development/systemapi.io/systemapi-agent && go mod tidy
```

---

## Architecture Patterns

### System Architecture Diagram

```
WebSocket (dashboard)
        |
        v
[main.go: processIncomingMessage]
        |
        +-- "sysscript" --> [SysscriptEngine.Execute(script)]
        |                         |
        |                    thread.Load = loadFromScriptsDir (NEW)
        |                         |
        |                    starlark.ExecFile(thread, ...)
        |                         |
        |                    buildSysModule() (MODIFIED)
        |                         |
        |              +----------+----------+
        |              |          |          |
        |         [sys.containers] [sys.k3s]  [sys.exec, sys.fs, ...]
        |              |          |
        |         dockerClient  k3sClient
        |              |          |
        |         /var/run/     kubeconfig
        |         docker.sock   TLS client
        |
        +-- "telemetry" (5s ticker)
                  |
             gatherTelemetry() (MODIFIED)
                  |
            +-----+-----+
            |           |
        dockerClient  k3sClient
            |           |
        DockerStats  K3SStats
            |           |
        TelemetryPayload.Docker  .K3S  (proto-aligned)
                  |
             WebSocket send
```

### Recommended Project Structure

New files to create in `/Users/ryan/development/systemapi.io/systemapi-agent/`:

```
systemapi-agent/
├── main.go                # (existing) CommandMessage, WebSocket loop
├── sysscript.go           # (MODIFY) Entitlements + AllowContainers/AllowK3s; buildSysModule() conditionals; thread.Load
├── telemetry.go           # (MODIFY) TelemetryPayload adds Docker/K3S fields; gatherTelemetry() populates them
├── sys_containers.go      # (NEW) containersListFn, containersStatsFn, containersStopFn, etc.
├── sys_k3s.go             # (NEW) k3sNodesFn, k3sPodsFn, k3sApplyFn
├── docker_client.go       # (NEW) DockerClient struct: Unix socket transport, list/stats/start/stop/restart
├── k3s_client.go          # (NEW) K3sClient struct: kubeconfig TLS client, nodes/pods/apply
├── sys_advanced.go        # (existing stub — containersRun stays but is superseded by sys_containers.go methods)
└── go.mod                 # (MODIFY) add require + replace for adsops-utils/gen/go
```

### Pattern 1: Entitlement-Conditional Module Inclusion (D-11)

**What:** In `buildSysModule()`, add `"containers"` and `"k3s"` keys to `sysDict` only when entitlements permit.
**When to use:** All new Starlark modules that require entitlement gating.

```go
// Source: CONTEXT.md D-11; pattern derived from existing buildSysModule() in sysscript.go
sysDict := starlark.StringDict{
    "net":      starlarkstruct.FromStringDict(starlark.String("net"), sysNet),
    "exec":     starlarkstruct.FromStringDict(starlark.String("exec"), sysExec),
    // ... existing modules ...
}

if engine.Entitlements.AllowContainers {
    sysContainers := starlark.StringDict{
        "list":    starlark.NewBuiltin("list", engine.containersList),
        "stats":   starlark.NewBuiltin("stats", engine.containersStats),
        "stop":    starlark.NewBuiltin("stop", engine.containersStop),
        "start":   starlark.NewBuiltin("start", engine.containersStart),
        "restart": starlark.NewBuiltin("restart", engine.containersRestart),
    }
    sysDict["containers"] = starlarkstruct.FromStringDict(starlark.String("containers"), sysContainers)
}

if engine.Entitlements.AllowK3s {
    sysK3s := starlark.StringDict{
        "nodes":  starlark.NewBuiltin("nodes", engine.k3sNodes),
        "pods":   starlark.NewBuiltin("pods", engine.k3sPods),
        "apply":  starlark.NewBuiltin("apply", engine.k3sApply),
    }
    sysDict["k3s"] = starlarkstruct.FromStringDict(starlark.String("k3s"), sysK3s)
}
```

### Pattern 2: Raw HTTP over Docker Unix Socket (D-03)

**What:** Custom `http.Transport` that dials the Unix socket, used for all Docker API calls.
**When to use:** Any Docker Engine API call.

```go
// Source: Go stdlib net/http documentation; Docker API convention [VERIFIED: docs.docker.com]
func newDockerTransport(socketPath string) *http.Transport {
    return &http.Transport{
        DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
            return (&net.Dialer{}).DialContext(ctx, "unix", socketPath)
        },
    }
}

// Usage: GET /v1.41/containers/json
client := &http.Client{Transport: newDockerTransport(socketPath), Timeout: 10 * time.Second}
resp, err := client.Get("http://localhost/v1.41/containers/json")
// Note: hostname is ignored for unix transport; "localhost" is a placeholder
```

### Pattern 3: Thread.Load for Sysscript Library Loading (D-07, D-08, D-09)

**What:** Set `thread.Load` on the `starlark.Thread` before calling `starlark.ExecFile`. The loader reads files from `/etc/systemapi/scripts/` relative to the load path.
**When to use:** Every script execution in `Execute()`.

```go
// Source: Context7 /google/starlark-go — Thread.Load example [VERIFIED: Context7]
// The cache prevents re-executing already-loaded modules in the same script run.
func (engine *SysscriptEngine) Execute(scriptSource string) (string, error) {
    var outBuffer bytes.Buffer
    cache := make(map[string]starlark.StringDict)
    const scriptsBase = "/etc/systemapi/scripts"

    var loadFn func(thread *starlark.Thread, module string) (starlark.StringDict, error)
    loadFn = func(thread *starlark.Thread, module string) (starlark.StringDict, error) {
        if cached, ok := cache[module]; ok {
            return cached, nil
        }
        path := filepath.Join(scriptsBase, module)
        src, err := os.ReadFile(path)
        if err != nil {
            return nil, fmt.Errorf("load(%q): %w", module, err)
        }
        moduleThread := &starlark.Thread{Name: "load " + module, Load: loadFn}
        globals, err := starlark.ExecFile(moduleThread, module, src, nil)
        if err != nil {
            return nil, err
        }
        cache[module] = globals
        return globals, nil
    }

    thread := &starlark.Thread{
        Name:  "Sysscript",
        Print: func(_ *starlark.Thread, msg string) { outBuffer.WriteString(msg + "\n") },
        Load:  loadFn,
    }
    // ... rest of Execute unchanged
}
```

### Pattern 4: Kubernetes Raw HTTP with TLS from kubeconfig (D-04, D-06)

**What:** Parse kubeconfig YAML (already have `gopkg.in/yaml.v3`), extract server URL + CA cert + client cert + client key, build `*http.Client` with TLS config.
**When to use:** All k3s API calls.

```go
// Source: Go stdlib crypto/tls, crypto/x509 [ASSUMED - standard Go TLS pattern]
// kubeconfig YAML structure is standard; gopkg.in/yaml.v3 already in go.mod
type KubeconfigCluster struct {
    Server                   string `yaml:"server"`
    CertificateAuthorityData []byte `yaml:"certificate-authority-data"`
}
// ... (parse clusters[0].cluster, users[0].user for client cert/key)

func buildK3sClient(kubeconfigPath string) (*http.Client, string, error) {
    data, err := os.ReadFile(kubeconfigPath)
    // parse YAML, extract CA, clientCert, clientKey, server
    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCertPEM)
    tlsCert, err := tls.X509KeyPair(clientCertPEM, clientKeyPEM)
    tlsConfig := &tls.Config{
        RootCAs:      caCertPool,
        Certificates: []tls.Certificate{tlsCert},
    }
    transport := &http.Transport{TLSClientConfig: tlsConfig}
    return &http.Client{Transport: transport, Timeout: 10 * time.Second}, serverURL, nil
}
```

### Pattern 5: Starlark Return Value — List of Structs

**What:** Return a `*starlark.List` of `*starlarkstruct.Struct` values from Starlark builtins.
**When to use:** `sys.containers.list()`, `sys.k3s.nodes()`, `sys.k3s.pods()`.

```go
// Source: Existing pattern in sys_net_proc.go (procList) [VERIFIED: codebase]
var items []starlark.Value
for _, c := range containers {
    d := starlark.StringDict{
        "id":    starlark.String(c.Id),
        "name":  starlark.String(c.Name),
        "image": starlark.String(c.Image),
        "state": starlark.String(c.State),
    }
    items = append(items, starlarkstruct.FromStringDict(starlark.String("container"), d))
}
return starlark.NewList(items), nil
```

### Anti-Patterns to Avoid

- **Inline entitlement guard for containers/k3s:** `if !engine.Entitlements.AllowContainers { return error }` inside the method — this still registers the namespace in `sysDict`. Use the buildSysModule conditional-include approach (D-11).
- **Moby/docker SDK import:** Adding `github.com/docker/docker/client` violates success criteria #1 and D-03.
- **client-go import for k3s:** Adds ~20 transitive dependencies. Parse kubeconfig with yaml.v3 and build a raw HTTP client.
- **proto type as TelemetryPayload replacement:** The local `TelemetryPayload` struct and the proto-generated one cannot be used interchangeably without friction (proto has internal state fields). Add local `DockerStats`/`K3SStats`-shaped structs that mirror the proto JSON tags, or use the proto structs directly after adding the replace directive.
- **Streaming Docker stats:** `GET /containers/{id}/stats` without `?stream=false` streams forever. Always append `?stream=false`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Kubeconfig YAML parsing | Custom YAML parser | `gopkg.in/yaml.v3` (already in go.mod) | kubeconfig has nested anchors/refs |
| CPU % from Docker stats | Custom delta logic | Formula: `(cpu_delta/system_delta)*num_cpus*100` | Docker stats return raw counters; need two reads for rate |
| Starlark module assembly | Custom struct type | `starlarkstruct.FromStringDict` | Already used throughout; provides correct Starlark attribute access |
| Proto import wiring | Duplicate struct definitions | `go.mod replace` directive | gen/go has its own go.mod; replace is the standard local module pattern |
| TLS from kubeconfig | Hand-roll cert parsing | `crypto/tls` + `crypto/x509` stdlib | Standard library handles PEM decoding, key pair loading |

---

## Docker Engine API Reference

### Endpoints Used

| Operation | Method + Path | Query Params | Response Notes |
|-----------|--------------|--------------|----------------|
| List containers | `GET /v1.41/containers/json` | `all=true` to include stopped | JSON array: `Id`, `Names`, `Image`, `State`, `Status` |
| Container stats | `GET /v1.41/containers/{id}/stats` | `stream=false` (required) | `cpu_stats`, `precpu_stats`, `memory_stats`, `networks` |
| Start container | `POST /v1.41/containers/{id}/start` | — | 204 No Content on success |
| Stop container | `POST /v1.41/containers/{id}/stop` | `t=10` (timeout seconds) | 204 No Content |
| Restart container | `POST /v1.41/containers/{id}/restart` | `t=10` (timeout seconds) | 204 No Content |

**CPU % calculation from stats:** [VERIFIED: oneuptime.com blog + Docker API convention]

```
cpu_delta = cpu_stats.cpu_usage.total_usage - precpu_stats.cpu_usage.total_usage
system_delta = cpu_stats.system_cpu_usage - precpu_stats.system_cpu_usage
cpu_pct = (cpu_delta / system_delta) * cpu_stats.online_cpus * 100.0
```

**Memory % calculation:**

```
mem_pct = float64(memory_stats.usage) / float64(memory_stats.limit) * 100.0
```

**Network I/O:** The `networks` field is a map; iterate all interfaces and sum `rx_bytes`/`tx_bytes`. These are cumulative counters (not rates) — for rate computation use delta over time interval.

**Docker socket path resolution (D-01):**

```go
func dockerSocketPath() string {
    if h := os.Getenv("DOCKER_HOST"); h != "" {
        // DOCKER_HOST may be "unix:///path/to/docker.sock"
        if strings.HasPrefix(h, "unix://") {
            return strings.TrimPrefix(h, "unix://")
        }
        return h
    }
    return "/var/run/docker.sock"
}
```

### Kubernetes API Endpoints Used

| Operation | Method + Path | Notes |
|-----------|--------------|-------|
| List nodes | `GET /api/v1/nodes` | Returns `items[]` with `metadata.name`, `status.conditions` |
| List pods (all namespaces) | `GET /api/v1/pods` | Returns `items[]` with `metadata.namespace`, `status.phase` |
| List pods (namespace) | `GET /api/v1/namespaces/{ns}/pods` | Namespace-scoped |
| Apply YAML (create/update) | `POST /api/v1/namespaces/{ns}/{resource}` or `PATCH` | D-06: implement as POST (create) or PATCH (strategic merge) |

**kubeconfig file structure (standard k3s install):**

```yaml
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: <base64 PEM>
    server: https://127.0.0.1:6443
  name: default
users:
- user:
    client-certificate-data: <base64 PEM>
    client-key-data: <base64 PEM>
  name: default
```

Note: `certificate-authority-data`, `client-certificate-data`, and `client-key-data` are base64-encoded PEM blocks. Decode with `base64.StdEncoding.DecodeString` before passing to `x509`/`tls`.

---

## Telemetry Extension (AGENT-05, AGENT-06)

### Current vs Required TelemetryPayload

The existing local `TelemetryPayload` struct in `telemetry.go` has fields: `Timestamp`, `Host`, `CPU`, `Memory`, `Disk`, `Network`, `Software`. It does NOT have Docker or k3s fields.

The proto-generated `TelemetryPayload` (in `adsops-utils/gen/go/adsops/v1/telemetry.pb.go`) has:

```go
type TelemetryPayload struct {
    Timestamp  int64          // field 1
    HostId     string         // field 2
    HostInfo   *HostInfo      // field 3
    Cpu        *CpuMetrics    // field 4
    Memory     *MemoryMetrics // field 5
    Disk       []*DiskMetrics // field 6
    Network    *NetworkMetrics // field 7
    Software   []*SoftwareInfo // field 8
    Docker     *DockerStats   // field 9 (NEW)
    K3S        *K3SStats      // field 10 (NEW)
}
```

### Approach Options for D-12

Two viable approaches — Claude's discretion to choose:

**Option A (Recommended): Add Docker/K3s fields to local struct, keep local types**

Add `Docker *LocalDockerStats` and `K3s *LocalK3sStats` to the existing local `TelemetryPayload`. Define local structs with JSON tags matching the proto JSON tags (`json:"docker"`, `json:"k3s"`). Avoids proto dependency in `telemetry.go` itself — the proto replace directive is only needed for explicit proto encoding (not needed since telemetry is sent as JSON over WebSocket).

**Option B: Import proto types directly**

Replace local struct with proto-generated type. Requires the `go.mod replace` directive to be wired first. Proto structs have internal `protoimpl.MessageState` fields that are harmless for JSON marshaling but add complexity. The `HostInfo` name collision (local vs proto) needs resolution.

**Recommendation:** Option A — add local `DockerStats` and `K3sStats` mirror structs with matching JSON tags. This avoids the name collision (`telemetry.go` already defines `HostInfo`, `CPUMetrics`, etc. locally) and keeps the proto replace directive scoped only to where it's explicitly needed. The JSON output will be structurally compatible.

### Local Mirror Struct Shape

```go
// In telemetry.go — mirrors proto DockerStats JSON shape [CITED: proto/adsops/v1/container.proto]
type ContainerStatsTelemetry struct {
    Id            string  `json:"id"`
    Name          string  `json:"name"`
    Image         string  `json:"image"`
    State         string  `json:"state"`
    CpuPct        float64 `json:"cpu_pct"`
    MemUsedBytes  int64   `json:"mem_used_bytes"`
    MemLimitBytes int64   `json:"mem_limit_bytes"`
    MemPct        float64 `json:"mem_pct"`
    RxBytesPerSec float64 `json:"rx_bytes_per_sec"`
    TxBytesPerSec float64 `json:"tx_bytes_per_sec"`
    RestartCount  int32   `json:"restart_count"`
}

type DockerStatsTelemetry struct {
    Available         bool                       `json:"available"`
    TotalContainers   int32                      `json:"total_containers"`
    RunningContainers int32                      `json:"running_containers"`
    Containers        []ContainerStatsTelemetry  `json:"containers"`
}

// mirrors proto K3sStats JSON shape [CITED: proto/adsops/v1/k3s.proto]
type NodeInfoTelemetry struct {
    Name    string `json:"name"`
    Role    string `json:"role"`
    Status  string `json:"status"`
    Version string `json:"version"`
}

type K3sStatsTelemetry struct {
    Available   bool                `json:"available"`
    TotalNodes  int32               `json:"total_nodes"`
    ReadyNodes  int32               `json:"ready_nodes"`
    TotalPods   int32               `json:"total_pods"`
    RunningPods int32               `json:"running_pods"`
    FailedPods  int32               `json:"failed_pods"`
    Nodes       []NodeInfoTelemetry `json:"nodes"`
}
```

---

## Common Pitfalls

### Pitfall 1: Docker Stats Stream (AGENT-02)

**What goes wrong:** `GET /containers/{id}/stats` without `?stream=false` opens a streaming response that never returns. The `http.Client.Do()` call blocks forever.
**Why it happens:** Docker's stats endpoint defaults to streaming mode.
**How to avoid:** Always append `?stream=false` to the stats URL.
**Warning signs:** `http.Client` call never returns; goroutine leak visible in runtime metrics.

### Pitfall 2: CPU % Requires Two Data Points

**What goes wrong:** A single Docker stats snapshot returns raw nanosecond counters, not percentages. Dividing `total_usage / system_cpu_usage` without a previous snapshot gives a meaningless ratio.
**Why it happens:** Docker stats API design — raw counters only.
**How to avoid:** The `?stream=false` response still includes both `cpu_stats` (current) and `precpu_stats` (previous) in a single response body. Use the delta between them — no need to call twice.
**Warning signs:** CPU% always appears as 0% or 100%.

### Pitfall 3: kubeconfig base64-encoded Fields

**What goes wrong:** `certificate-authority-data` in kubeconfig is base64-encoded PEM, not raw PEM. Passing the base64 string directly to `x509.NewCertPool().AppendCertsFromPEM()` fails silently (returns false) — no error, but TLS verification fails.
**Why it happens:** Standard kubeconfig format for inline certs.
**How to avoid:** `base64.StdEncoding.DecodeString(certData)` before passing to x509/tls functions.
**Warning signs:** TLS handshake failures; `x509: certificate signed by unknown authority`.

### Pitfall 4: Starlark Module Namespace Absent vs Empty

**What goes wrong:** If `"containers"` is still in `sysDict` but points to an empty struct, scripts can reference `sys.containers` without error — the entitlement is not enforced.
**Why it happens:** Confusing "empty module" with "absent key."
**How to avoid:** D-11 pattern — conditionally add the key to `sysDict` only when entitled. If absent, `sys.containers` in Starlark raises `AttributeError`.
**Warning signs:** Success criteria #6 test passes even without entitlement.

### Pitfall 5: Thread.Load Module Thread Needs Load Too

**What goes wrong:** The sub-thread created for loading a module (`moduleThread := &starlark.Thread{...}`) doesn't have `Load` set. If the loaded module itself calls `load()`, it fails with "load not supported."
**Why it happens:** Each new `starlark.Thread` starts with nil `Load`.
**How to avoid:** Set `Load: loadFn` on the `moduleThread` too (see Pattern 3 above — the `loadFn` is recursive).
**Warning signs:** Nested `load()` calls fail; top-level `load()` works fine.

### Pitfall 6: Local TelemetryPayload HostInfo Name Collision

**What goes wrong:** `telemetry.go` already defines a local `type HostInfo struct`. The proto package also defines `HostInfo`. If the proto package is imported directly into `telemetry.go`, there's a type name collision at compile time.
**Why it happens:** Proto types mirror local struct names.
**How to avoid:** Use Option A (mirror structs with distinct local names) or import proto with alias `adsopsv1 "github.com/afterdarksys/adsops-utils/gen/go/adsops/v1"` and use qualified names.
**Warning signs:** `HostInfo redeclared in this block` compile error.

### Pitfall 7: Docker Socket Check on Startup vs Per-Call

**What goes wrong:** Checking socket existence once at startup and caching "unavailable" — but Docker might not be running at agent start and could start later.
**Why it happens:** Eager initialization.
**How to avoid:** Attempt the socket connection per-call (or per-telemetry-tick). Per D-02, failures are non-fatal and logged.

---

## Code Examples

### Docker Unix Socket Transport

```go
// Source: Go net/http stdlib; Docker API convention [VERIFIED: Docker docs + Go stdlib]
import (
    "context"
    "net"
    "net/http"
    "time"
)

func newUnixSocketClient(socketPath string) *http.Client {
    return &http.Client{
        Timeout: 10 * time.Second,
        Transport: &http.Transport{
            DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
                return (&net.Dialer{}).DialContext(ctx, "unix", socketPath)
            },
        },
    }
}

// List containers: GET http://localhost/v1.41/containers/json?all=true
// Note: hostname "localhost" is ignored by unix transport; use any value
```

### Thread.Load Wiring in Execute()

```go
// Source: Context7 /google/starlark-go Thread.Load example [VERIFIED: Context7]
const scriptsBase = "/etc/systemapi/scripts"

cache := make(map[string]starlark.StringDict)
var loadFn func(*starlark.Thread, string) (starlark.StringDict, error)
loadFn = func(thread *starlark.Thread, module string) (starlark.StringDict, error) {
    if g, ok := cache[module]; ok {
        return g, nil
    }
    src, err := os.ReadFile(filepath.Join(scriptsBase, module))
    if err != nil {
        return nil, fmt.Errorf("load(%q): %w", module, err)
    }
    mt := &starlark.Thread{Name: "load " + module, Load: loadFn}
    g, err := starlark.ExecFile(mt, module, src, nil)
    if err != nil {
        return nil, err
    }
    cache[module] = g
    return g, nil
}

thread := &starlark.Thread{
    Name:  "Sysscript",
    Print: func(_ *starlark.Thread, msg string) { outBuffer.WriteString(msg + "\n") },
    Load:  loadFn,
}
```

### Builtin Returning Empty List on Error (D-02, D-05)

```go
// Source: Established codebase pattern + CONTEXT.md D-02 [VERIFIED: codebase]
func (engine *SysscriptEngine) containersList(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    containers, err := engine.dockerClient.ListContainers()
    if err != nil {
        log.Printf("[containers.list] Docker unavailable: %v", err)
        return starlark.NewList(nil), nil   // non-fatal: return empty list
    }
    var items []starlark.Value
    for _, c := range containers {
        d := starlark.StringDict{
            "id":    starlark.String(c.Id),
            "name":  starlark.String(c.Name),
            "image": starlark.String(c.Image),
            "state": starlark.String(c.State),
        }
        items = append(items, starlarkstruct.FromStringDict(starlark.String("container"), d))
    }
    return starlark.NewList(items), nil
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Moby Docker SDK (`github.com/docker/docker/client`) | Raw HTTP over Unix socket | D-03 (this phase) | No new large dependency; matches Docker CLI DOCKER_HOST convention |
| `k8s.io/client-go` for k8s access | Raw HTTP with TLS from kubeconfig | D-06 (this phase) | Avoids ~100 transitive deps; sufficient for read-only nodes/pods |
| Starlark without `load()` | `Thread.Load` wired to `/etc/systemapi/scripts/` | D-08 (this phase) | Enables modular sysscript libraries (Phase 4 dependency) |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Docker API version `v1.41` is supported by the target hosts' Docker daemons | Standard Stack / Docker API Reference | If hosts run Docker < 20.10 (pre-v1.41), use a lower version or negotiate via `/version` endpoint |
| A2 | kubeconfig `certificate-authority-data` is always base64-encoded (not a file path) | Common Pitfalls #3 | If some k3s configs use `certificate-authority` (file path), need to add file-path fallback |
| A3 | `sys.k3s.apply(yaml_str)` can use a simple POST to create or PATCH for update; exact resource type parsing from YAML is caller's responsibility | Pattern 4 / k3s API | If the apply semantics need server-side apply or strategic merge patch, implementation is more complex |
| A4 | The agent runs as root (or has Docker socket access) on the target host | Docker socket access | If agent runs as non-root without docker group, socket access fails; deployment DaemonSet (Phase 6) handles this via volume mounts |
| A5 | `TelemetryPayload` in the proto uses `K3S *K3SStats` (uppercase) but the JSON tag is `k3s` | Telemetry Extension | Minor — confirmed from generated code; use Option A mirror structs to avoid the naming issue entirely |

---

## Open Questions

1. **Docker API version negotiation vs hardcoded v1.41**
   - What we know: D-03 leaves this to Claude's discretion. v1.41 corresponds to Docker Engine 20.10+ which is widely deployed.
   - What's unclear: Target host Docker versions. Some hosts may be newer (v1.45+) or older.
   - Recommendation: Hardcode `v1.41` for simplicity — it's a minimum baseline API version that has all needed endpoints. Docker daemons are forward-compatible.

2. **Caching Docker/k3s data between telemetry ticks**
   - What we know: Left to Claude's discretion. Telemetry runs every 5s. Docker stats call is fast (single HTTP round-trip over Unix socket).
   - What's unclear: Whether 5s polling overhead is a concern on resource-constrained edge hosts.
   - Recommendation: Re-query every tick (no caching). Simpler code. The stats call hits local socket with negligible overhead. Mirrors how `gatherSoftware()` is already cached separately (every 5min), not how base metrics work.

3. **`sys.k3s.apply(yaml_str)` — which Kubernetes resource types?**
   - What we know: D-06 says implement as raw HTTP PATCH/POST. The function takes a YAML string.
   - What's unclear: How to route to the correct API group/resource from a generic YAML string.
   - Recommendation: Parse the `kind` and `apiVersion` from the YAML to determine the endpoint. For Phase 3, support core v1 resources (ConfigMap, Pod) and `apps/v1` (Deployment). Document that the implementation does not do full `kubectl apply` semantics — it's a POST (create) with a conflict fallback to PATCH.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Go toolchain | Building agent | ✓ | go1.26.2 (>= go1.25.7 required) | — |
| Docker CLI / daemon | Testing AGENT-01–03 | ✓ (docker 29.3.1) | 29.3.1 | Integration tests skipped on hosts without Docker |
| kubectl | Testing AGENT-04 | ✓ | v1.35.0 | — |
| Docker socket `/var/run/docker.sock` | Runtime (agent host) | ✗ (dev machine) | — | Tests mock HTTP; Docker socket on target Linux hosts |
| k3s kubeconfig `/etc/rancher/k3s/k3s.yaml` | Runtime (agent host) | ✗ (dev machine) | — | Tests mock HTTP; k3s on target Linux hosts |
| adsops-utils `gen/go/` | go.mod replace | ✓ at `/Users/ryan/development/adsops-utils/gen/go` | local | — |

**Missing dependencies with no fallback:**
- Docker socket and k3s kubeconfig are not available on the dev machine but will be present on target hosts. Unit tests must not require them — use interface injection or function variable for the HTTP client so tests can provide a mock `httptest.Server`.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

> `workflow.nyquist_validation` not explicitly set to false in config.json — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Go testing stdlib (`go test`) |
| Config file | None — standard Go test runner |
| Quick run command | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test ./... -run TestContainers -v` |
| Full suite command | `cd /Users/ryan/development/systemapi.io/systemapi-agent && go test ./... -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGENT-01 | `sys.containers.list()` returns list from mocked Docker API | unit | `go test ./... -run TestContainersList` | ❌ Wave 0 |
| AGENT-02 | `sys.containers.stats(id)` returns CPU/mem/net struct | unit | `go test ./... -run TestContainersStats` | ❌ Wave 0 |
| AGENT-03 | `sys.containers.stop/start/restart` call correct Docker endpoints | unit | `go test ./... -run TestContainersControl` | ❌ Wave 0 |
| AGENT-04 | `sys.k3s.nodes()` and `sys.k3s.pods()` return parsed data from mocked k8s API | unit | `go test ./... -run TestK3sModule` | ❌ Wave 0 |
| AGENT-05 | `gatherTelemetry()` result includes non-nil `Docker` and `K3s` fields when available | unit | `go test ./... -run TestTelemetryExtended` | ❌ Wave 0 |
| AGENT-06 | JSON tags of local telemetry structs match proto JSON tags | unit | `go test ./... -run TestTelemetryStructTags` | ❌ Wave 0 |
| AGENT-01 (entitlement) | `sys.containers` absent from Starlark env when `AllowContainers=false` | unit | `go test ./... -run TestEntitlementContainers` | ❌ Wave 0 |
| AGENT-04 (entitlement) | `sys.k3s` absent from Starlark env when `AllowK3s=false` | unit | `go test ./... -run TestEntitlementK3s` | ❌ Wave 0 |
| Thread.Load | `load("lib/helper.star", "fn")` resolves correctly from test fixture dir | unit | `go test ./... -run TestThreadLoad` | ❌ Wave 0 |

### Test Strategy Notes

- Docker and k3s clients must be injectable (interface or function variable) so tests can use `httptest.NewUnstartedServer` + a custom listener (or a local TCP server) to mock API responses.
- Starlark execution tests: construct a `SysscriptEngine` with mock client, call `Execute(scriptSource)`, assert on output string.
- Thread.Load test: create a temp directory with a `.star` fixture file, override `scriptsBase` constant (or make it a field), call `Execute` with a `load()` statement.

### Wave 0 Gaps

- [ ] `sys_containers_test.go` — covers AGENT-01, AGENT-02, AGENT-03, entitlement
- [ ] `sys_k3s_test.go` — covers AGENT-04, entitlement
- [ ] `telemetry_test.go` — covers AGENT-05, AGENT-06
- [ ] `sysscript_test.go` — covers Thread.Load wiring

---

## Security Domain

> `security_enforcement` not set in config — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | WebSocket already authenticated via api_key |
| V3 Session Management | No | Stateless agent |
| V4 Access Control | Yes | Entitlement enforcement via `AllowContainers`/`AllowK3s` in buildSysModule() |
| V5 Input Validation | Yes | `starlark.UnpackArgs` for all builtin args; container IDs passed to Docker API should be validated as alphanumeric+dash |
| V6 Cryptography | Yes | TLS from kubeconfig (stdlib crypto/tls) — never hand-rolled |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unapproved container control (stop/start arbitrary containers) | Elevation of Privilege | Entitlement `AllowContainers` absent = namespace not in Starlark env |
| Container ID injection (e.g., path traversal via `/../../etc/passwd`) | Tampering | Docker API accepts only container IDs/names; validate input is `[a-zA-Z0-9_-]+` before URL construction |
| Script loading path traversal (`load("../../etc/passwd", "x")`) | Information Disclosure | `filepath.Join(scriptsBase, module)` — verify the joined path stays under `scriptsBase` with `strings.HasPrefix(filepath.Clean(joinedPath), scriptsBase)` |
| k3s `apply(yaml_str)` — applying arbitrary k8s resources | Elevation of Privilege | Entitlement `AllowK3s` required; for Phase 3, document that apply is unrestricted within the entitlement |
| Docker stats endpoint leaking container internals | Information Disclosure | Mitigated by entitlement; `sys.containers` requires `AllowContainers` |

**Path traversal in Thread.Load is a new attack surface.** The load path resolution must explicitly check that the resolved path is within `scriptsBase`:

```go
resolved := filepath.Clean(filepath.Join(scriptsBase, module))
if !strings.HasPrefix(resolved, scriptsBase+string(os.PathSeparator)) {
    return nil, fmt.Errorf("load(%q): path traversal not allowed", module)
}
```

---

## Sources

### Primary (HIGH confidence)

- Context7 `/google/starlark-go` — Thread.Load callback, ExecFile, module cache pattern [VERIFIED]
- `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — existing patterns for buildSysModule, Execute, Entitlements struct [VERIFIED: codebase]
- `/Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go` — TelemetryPayload local struct [VERIFIED: codebase]
- `/Users/ryan/development/adsops-utils/gen/go/adsops/v1/telemetry.pb.go` — proto TelemetryPayload with Docker/K3S fields [VERIFIED: codebase]
- `/Users/ryan/development/adsops-utils/proto/adsops/v1/container.proto` and `k3s.proto` — canonical proto field definitions [VERIFIED: codebase]
- `/Users/ryan/development/systemapi.io/systemapi-agent/go.mod` — current dependencies [VERIFIED: codebase]
- `/Users/ryan/development/adsops-utils/gen/go/go.mod` — module path for replace directive [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- [oneuptime.com Docker stats API article](https://oneuptime.com/blog/post/2026-02-08-how-to-get-docker-container-statistics-in-json-format/view) — Docker stats JSON fields (`cpu_stats`, `precpu_stats`, `memory_stats`, `networks`) and CPU % formula [CITED]
- [Docker Engine API docs](https://docs.docker.com/reference/api/engine/version/v1.41/) — endpoint paths and HTTP methods [CITED]
- [Kubernetes docs — Access Cluster API](https://kubernetes.io/docs/tasks/administer-cluster/access-cluster-api/) — raw HTTP access pattern with kubeconfig [CITED]

### Tertiary (LOW confidence)

- General training knowledge on kubeconfig YAML structure and base64-encoded cert fields — tagged [ASSUMED] where applicable

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all key deps verified in go.mod; no new deps required except proto replace
- Architecture: HIGH — codebase read directly; patterns extracted from existing source files
- Docker API: MEDIUM — endpoint paths from docs; stats field structure from secondary source
- k3s/k8s raw HTTP: MEDIUM — standard Go TLS pattern well-established; kubeconfig structure standard
- Pitfalls: HIGH — derived from code analysis and verified API behavior

**Research date:** 2026-05-04
**Valid until:** 2026-08-04 (Docker/k3s APIs are stable; Starlark API is stable)
