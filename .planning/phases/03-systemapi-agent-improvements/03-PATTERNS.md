# Phase 3: systemapi-agent Improvements - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 7 (2 new Go files for Starlark builtins, 2 new Go files for HTTP clients, 2 modified Go files, 1 modified go.mod)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `sys_containers.go` (NEW) | service / starlark-builtin | request-response (HTTP over Unix socket) | `sys_net_proc.go` — procList, procFind, procKill | exact (same builtin signature, list-return pattern, entitlement gate) |
| `sys_k3s.go` (NEW) | service / starlark-builtin | request-response (HTTPS REST) | `sys_net_proc.go` — procList, procFind | role-match (same builtin pattern; different transport) |
| `docker_client.go` (NEW) | utility / HTTP client | request-response | `sys_net_proc.go` — uses net.DialTimeout directly; closest non-stdlib analog | partial (no existing standalone HTTP client file; Unix socket is new) |
| `k3s_client.go` (NEW) | utility / HTTP client | request-response | `sys_config.go` — uses yaml.v3 for parsing; `sys_net_proc.go` for HTTP pattern | partial (kubeconfig TLS parsing is new; yaml.v3 already used) |
| `sysscript.go` (MODIFY) | engine / orchestrator | event-driven | `sysscript.go` itself — Entitlements struct, buildSysModule(), Execute() | self (direct modification) |
| `telemetry.go` (MODIFY) | service / data collector | batch (5s tick) | `telemetry.go` itself — TelemetryPayload struct, gatherTelemetry() | self (direct modification) |
| `go.mod` (MODIFY) | config | — | `go.mod` itself | self (direct modification) |

---

## Pattern Assignments

### `sys_containers.go` (NEW — starlark-builtin, request-response)

**Analog:** `sys_net_proc.go` (procList, procFind, procKill patterns) and `sys_advanced.go` (containersRun stub to replace)

**Imports pattern** (`sys_net_proc.go` lines 1-12, `sys_advanced.go` lines 1-8):
```go
package main

import (
    "fmt"
    "log"

    "go.starlark.net/starlark"
    "go.starlark.net/starlarkstruct"
)
```
Note: `starlarkstruct` is imported in `sysscript.go` lines 15-16 — import it here too since container list returns structs (not dicts, per Pattern 5 in RESEARCH.md).

**Core builtin signature pattern** (`sys_net_proc.go` lines 132-147):
```go
func (engine *SysscriptEngine) procList(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    procs, err := process.Processes()
    if err != nil {
        return starlark.None, fmt.Errorf("proc.list: %w", err)
    }

    results := make([]starlark.Value, 0, len(procs))
    for _, p := range procs {
        d, err := procToDict(p)
        if err != nil {
            continue // skip processes that vanished or lack permissions
        }
        results = append(results, d)
    }
    return starlark.NewList(results), nil
}
```
For `containers.list()`, replace `process.Processes()` with `engine.dockerClient.ListContainers()` and replace the error path with non-fatal empty-list return (D-02):
```go
// D-02: non-fatal — return empty list and log
if err != nil {
    log.Printf("[containers.list] Docker unavailable: %v", err)
    return starlark.NewList(nil), nil
}
```

**UnpackArgs pattern for single-arg builtins** (`sys_net_proc.go` lines 152-159):
```go
func (engine *SysscriptEngine) procGet(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    var pid int
    if err := starlark.UnpackArgs("get", args, kwargs, "pid", &pid); err != nil {
        return starlark.None, err
    }
    // ...
}
```
Use this exact pattern for `containers.stats(id)`, `containers.stop(id)`, `containers.start(id)`, `containers.restart(id)` — replace `"pid"` with `"id"` and `int` with `string`.

**Returning a list of structs** (`sys_net_proc.go` lines 225-238 — procToDict builds a `*starlark.Dict`; for containers use `starlarkstruct.FromStringDict` per RESEARCH.md Pattern 5):
```go
// procToDict uses starlark.NewDict — for containers, use starlarkstruct.FromStringDict instead:
d := starlark.StringDict{
    "id":    starlark.String(c.Id),
    "name":  starlark.String(c.Name),
    "image": starlark.String(c.Image),
    "state": starlark.String(c.State),
}
items = append(items, starlarkstruct.FromStringDict(starlark.String("container"), d))
```

**Entitlement gate for destructive ops** (`sys_net_proc.go` lines 193-198 — procKill uses AllowExec gate):
```go
func (engine *SysscriptEngine) procKill(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    if !engine.Entitlements.AllowExec {
        return starlark.None, fmt.Errorf("security exception: exec entitlement required for proc.kill")
    }
    // ...
}
```
NOTE: Do NOT use this inline guard pattern for containers/k3s (see D-11 and Anti-Patterns). The entitlement for containers is enforced in `buildSysModule()` by not adding the key at all. The stop/start/restart methods themselves do NOT need an inline check.

**Logging pattern** (`sys_advanced.go` lines 19, 60, 77):
```go
log.Printf("[Agent -> Dashboard Alert] Severity: %s | Message: %s", severity, message)
log.Printf("[eBPF/ETW Hook] Subscribed to %s", eventType)
log.Printf("[Package Management] Installing %s", name)
```
Use consistent `[containers.list]`, `[containers.stats]`, `[k3s.nodes]` prefix style.

---

### `sys_k3s.go` (NEW — starlark-builtin, request-response)

**Analog:** `sys_net_proc.go` (procList, procFind patterns) — same builtin signature, same list-return, same UnpackArgs.

**Imports pattern:**
```go
package main

import (
    "fmt"
    "log"

    "go.starlark.net/starlark"
    "go.starlark.net/starlarkstruct"
)
```

**Core builtin pattern** — identical to `sys_containers.go` above. For `k3s.nodes()` (no args):
```go
func (engine *SysscriptEngine) k3sNodes(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    if err := starlark.UnpackArgs("nodes", args, kwargs); err != nil {
        return starlark.None, err
    }
    nodes, err := engine.k3sClient.ListNodes()
    if err != nil {
        log.Printf("[k3s.nodes] k3s unavailable: %v", err)
        return starlark.NewList(nil), nil  // D-05: non-fatal
    }
    // ... build starlark list of starlarkstruct items
}
```

For `k3s.pods(namespace)` (optional arg — copy optional arg pattern from `sys_net_proc.go` lines 16-21):
```go
var host, rrType string
if err := starlark.UnpackArgs("dns_lookup", args, kwargs, "host", &host, "type?", &rrType); err != nil {
    return starlark.None, err
}
// "?" suffix marks optional argument in UnpackArgs
```
Apply to `pods`: `"namespace?"` with empty string default meaning "all namespaces".

**Returning struct fields for k3s nodes:**
```go
d := starlark.StringDict{
    "name":    starlark.String(node.Name),
    "role":    starlark.String(node.Role),
    "status":  starlark.String(node.Status),
    "version": starlark.String(node.Version),
}
items = append(items, starlarkstruct.FromStringDict(starlark.String("node"), d))
```

**For `k3s.apply(yaml_str)` — returns dict with success/error** (copy pattern from `sys_config.go` lines 28-44):
```go
result := starlark.NewDict(2)
if err != nil {
    result.SetKey(starlark.String("success"), starlark.False)
    result.SetKey(starlark.String("error"), starlark.String(err.Error()))
} else {
    result.SetKey(starlark.String("success"), starlark.True)
    result.SetKey(starlark.String("error"), starlark.String(""))
}
return result, nil
```

---

### `docker_client.go` (NEW — utility/HTTP client, request-response)

**Analog:** No direct analog exists in the codebase for a Unix socket HTTP client. The net package is used directly in `sys_net_proc.go` lines 113-114 (`net.DialTimeout`) — this is the closest pattern for raw network dialing.

**Import pattern for stdlib net/http over Unix socket** (no existing codebase example; use RESEARCH.md Pattern 2):
```go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "net"
    "net/http"
    "os"
    "strings"
    "time"
)
```

**Struct definition pattern** — follow the same flat-package style as `software.go` lines 10-14:
```go
type SoftwareMetrics struct {
    Name         string `json:"name"`
    Version      string `json:"version"`
    Architecture string `json:"architecture,omitempty"`
}
```
DockerClient struct, DockerContainer struct, DockerStatsResponse struct all follow this style.

**net.Dial pattern** (`sys_net_proc.go` lines 111-114):
```go
addr := fmt.Sprintf("%s:%d", host, port)
start := time.Now()
conn, err := net.DialTimeout("tcp", addr, time.Duration(timeoutMs)*time.Millisecond)
```
The Docker Unix socket transport uses `net.Dialer.DialContext` instead of `DialTimeout` — same `net` package, different method:
```go
// From RESEARCH.md Pattern 2 (verified against Go stdlib):
func newDockerTransport(socketPath string) *http.Transport {
    return &http.Transport{
        DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
            return (&net.Dialer{}).DialContext(ctx, "unix", socketPath)
        },
    }
}
```

**HTTP client timeout pattern** (`sysscript.go` lines 241-243):
```go
client := &http.Client{Timeout: 10 * time.Second}
resp, err := client.Get(reqUrl)
```
Use the same 10-second timeout for DockerClient.

**Error logging on non-fatal failures** — copy from `main.go` lines 93-95:
```go
if err != nil {
    log.Println("Error gathering telemetry:", err)
    continue
}
```
For DockerClient methods: `log.Printf("[docker_client] %v", err)` then return zero value + err to caller.

---

### `k3s_client.go` (NEW — utility/HTTP client, request-response)

**Analog:** `sys_config.go` for `gopkg.in/yaml.v3` usage pattern (lines 10, and kubeconfig YAML parsing); `sysscript.go` lines 241-249 for the `http.Client` construction pattern.

**yaml.v3 import pattern** (`sys_config.go` lines 10-11):
```go
import (
    // ...
    "gopkg.in/yaml.v3"
)
```
K3sClient uses `yaml.v3` to parse the kubeconfig file — same import, no new dependency.

**Struct definition for kubeconfig parsing** — follow `software.go` / `telemetry.go` style:
```go
type kubeconfig struct {
    Clusters []struct {
        Cluster struct {
            Server                   string `yaml:"server"`
            CertificateAuthorityData string `yaml:"certificate-authority-data"`
        } `yaml:"cluster"`
    } `yaml:"clusters"`
    Users []struct {
        User struct {
            ClientCertificateData string `yaml:"client-certificate-data"`
            ClientKeyData         string `yaml:"client-key-data"`
        } `yaml:"user"`
    } `yaml:"users"`
}
```

**File reading pattern** (`sysscript.go` lines 275-279):
```go
data, err := os.ReadFile(path)
if err != nil {
    return starlark.None, err
}
```
K3sClient uses `os.ReadFile(kubeconfigPath)` — same pattern, same stdlib.

**Imports for k3s_client.go:**
```go
package main

import (
    "base64"
    "context"      // not used directly but needed for http.Transport DialContext style
    "crypto/tls"
    "crypto/x509"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
    "time"

    "gopkg.in/yaml.v3"
)
```

---

### `sysscript.go` (MODIFY — engine/orchestrator, event-driven)

**Modification 1: Entitlements struct** (`sysscript.go` lines 19-26):
```go
type Entitlements struct {
    AllowFSWrite       []string `json:"allow_fs_write"`
    AllowFSRead        []string `json:"allow_fs_read"`
    AllowNetOutbound   []string `json:"allow_net_outbound"`
    AllowExec          bool     `json:"allow_exec"`
    AllowConfigWrite   []string `json:"allow_config_write"`
    AllowServiceReload []string `json:"allow_service_reload"`
}
```
Add two new bool fields following the `AllowExec bool` pattern:
```go
AllowContainers bool `json:"allow_containers"`
AllowK3s        bool `json:"allow_k3s"`
```

**Modification 2: buildSysModule() — existing containers stub** (`sysscript.go` lines 106-108 and 166):
```go
sysContainers := starlark.StringDict{
    "run": starlark.NewBuiltin("run", engine.containersRun),
}
// ...
"containers": starlarkstruct.FromStringDict(starlark.String("containers"), sysContainers),
```
REMOVE the unconditional `sysContainers` block and the unconditional `"containers"` key from `sysDict`. Replace with conditional inclusion (D-11):
```go
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
        "nodes": starlark.NewBuiltin("nodes", engine.k3sNodes),
        "pods":  starlark.NewBuiltin("pods", engine.k3sPods),
        "apply": starlark.NewBuiltin("apply", engine.k3sApply),
    }
    sysDict["k3s"] = starlarkstruct.FromStringDict(starlark.String("k3s"), sysK3s)
}
```
Note: `sysDict` must be declared as a `starlark.StringDict` variable first, then keys added to it, then `starlarkstruct.FromStringDict` called at the end — currently `sysDict` is declared as a literal on line 158. Change to:
```go
sysDict := starlark.StringDict{
    "net":      starlarkstruct.FromStringDict(starlark.String("net"), sysNet),
    // ... all existing unconditional modules ...
}
// Then conditionally add containers and k3s:
if engine.Entitlements.AllowContainers { ... }
if engine.Entitlements.AllowK3s { ... }
return starlarkstruct.FromStringDict(starlark.String("sys"), sysDict)
```

**Modification 3: Execute() — Thread.Load wiring** (`sysscript.go` lines 42-63):
```go
func (engine *SysscriptEngine) Execute(scriptSource string) (string, error) {
    var outBuffer bytes.Buffer

    thread := &starlark.Thread{
        Name:  "Sysscript",
        Print: func(_ *starlark.Thread, msg string) { outBuffer.WriteString(msg + "\n") },
    }
    // ...
    _, err := starlark.ExecFile(thread, "sysscript.star", scriptSource, predeclared)
```
Add `Thread.Load` before the existing thread literal. The cache and loadFn must be declared above the thread (D-08):
```go
func (engine *SysscriptEngine) Execute(scriptSource string) (string, error) {
    var outBuffer bytes.Buffer

    const scriptsBase = "/etc/systemapi/scripts"
    cache := make(map[string]starlark.StringDict)
    var loadFn func(*starlark.Thread, string) (starlark.StringDict, error)
    loadFn = func(thread *starlark.Thread, module string) (starlark.StringDict, error) {
        if g, ok := cache[module]; ok {
            return g, nil
        }
        // D-09 + security: path traversal check
        resolved := filepath.Clean(filepath.Join(scriptsBase, module))
        if !strings.HasPrefix(resolved, scriptsBase+string(os.PathSeparator)) {
            return nil, fmt.Errorf("load(%q): path traversal not allowed", module)
        }
        src, err := os.ReadFile(resolved)
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
    // rest unchanged
```
Also add `"path/filepath"` and `"strings"` to the import block in `sysscript.go` (check: `strings` is already imported at line 11, `filepath` is not — add it).

**SysscriptEngine struct modification** — add client fields (follows same struct-field pattern as `cm *ConfigManager` on line 31):
```go
type SysscriptEngine struct {
    Entitlements *Entitlements
    cm           *ConfigManager
    dockerClient *DockerClient  // NEW: nil when !AllowContainers or Docker unavailable
    k3sClient    *K3sClient     // NEW: nil when !AllowK3s or k3s unavailable
}
```

---

### `telemetry.go` (MODIFY — service/data-collector, batch)

**Existing struct definition pattern** (`telemetry.go` lines 14-55):
```go
type TelemetryPayload struct {
    Timestamp   int64              `json:"timestamp"`
    Host        HostInfo           `json:"host"`
    CPU         CPUMetrics         `json:"cpu"`
    Memory      MemoryMetrics      `json:"memory"`
    Disk        []DiskMetrics      `json:"disk"`
    Network     NetworkMetrics     `json:"network"`
    Software    []SoftwareMetrics  `json:"software,omitempty"`
}
```
Add two new pointer fields (pointer so they are `null` in JSON when unavailable):
```go
Docker  *DockerStatsTelemetry `json:"docker,omitempty"`
K3s     *K3sStatsTelemetry    `json:"k3s,omitempty"`
```

**New struct definitions** — follow the same `json:"..."` tag style as existing structs (`telemetry.go` lines 24-55, `software.go` lines 10-14):
```go
// Mirrors proto DockerStats JSON shape (Option A from RESEARCH.md)
type ContainerStatsTelemetry struct {
    Id            string  `json:"id"`
    Name          string  `json:"name"`
    Image         string  `json:"image"`
    State         string  `json:"state"`
    CpuPct        float64 `json:"cpu_pct"`
    MemUsedBytes  int64   `json:"mem_used_bytes"`
    MemLimitBytes int64   `json:"mem_limit_bytes"`
    MemPct        float64 `json:"mem_pct"`
    RxBytes       uint64  `json:"rx_bytes"`
    TxBytes       uint64  `json:"tx_bytes"`
    RestartCount  int32   `json:"restart_count"`
}

type DockerStatsTelemetry struct {
    Available         bool                      `json:"available"`
    TotalContainers   int32                     `json:"total_containers"`
    RunningContainers int32                     `json:"running_containers"`
    Containers        []ContainerStatsTelemetry `json:"containers"`
}

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

**gatherTelemetry() extension pattern** (`telemetry.go` lines 62-153 — each section follows try-and-assign-or-skip):
```go
// Pattern: try, assign if no error, continue on error
hInfo, err := host.Info()
if err == nil {
    payload.Host = HostInfo{ ... }
}
```
Add Docker and k3s sections at the end (after Software, before `return`):
```go
// 7. Docker stats (non-fatal)
if dockerStats, err := gatherDockerStats(); err == nil {
    payload.Docker = dockerStats
} else {
    log.Printf("Docker stats unavailable: %v", err)
}

// 8. k3s stats (non-fatal)
if k3sStats, err := gatherK3sStats(); err == nil {
    payload.K3s = k3sStats
} else {
    log.Printf("k3s stats unavailable: %v", err)
}
```
The `gatherDockerStats()` and `gatherK3sStats()` functions live in `telemetry.go` and call into the respective client packages. They return `(*DockerStatsTelemetry, error)` and `(*K3sStatsTelemetry, error)`.

**Software caching pattern** (`telemetry.go` lines 56-59 and 144-150) — reference for whether to cache Docker/k3s:
```go
var lastSoftwareGather time.Time
var cachedSoftware []SoftwareMetrics

if now.Sub(lastSoftwareGather) > 5*time.Minute {
    cachedSoftware = gatherSoftware()
    lastSoftwareGather = now
}
```
Per RESEARCH.md Open Question 2 recommendation: do NOT cache Docker/k3s — re-query every 5s tick. The software caching pattern is used because software inventory is expensive (spawns shell commands); Docker stats hit a local socket and are cheap.

---

### `go.mod` (MODIFY)

**Existing require block** (`go.mod` lines 5-11):
```
require (
    github.com/creack/pty v1.1.24
    github.com/gorilla/websocket v1.5.3
    github.com/shirou/gopsutil/v3 v3.24.5
    go.starlark.net v0.0.0-20260210143700-b62fd896b91b
    gopkg.in/yaml.v3 v3.0.1
)
```
Add after the existing `require` block (per RESEARCH.md Standard Stack):
```
require github.com/afterdarksys/adsops-utils/gen/go v0.0.0

replace github.com/afterdarksys/adsops-utils/gen/go => /Users/ryan/development/adsops-utils/gen/go
```
Note: The proto replace directive is only needed if Option B (import proto types directly) is chosen. Per RESEARCH.md recommendation (Option A), the replace directive may not be required for Phase 3. Planner should confirm whether any file actually imports the proto package.

---

## Shared Patterns

### Starlark Builtin Method Signature
**Source:** `sys_net_proc.go` lines 132, 150, 165, 191 (all method definitions)
**Apply to:** All new methods in `sys_containers.go` and `sys_k3s.go`
```go
func (engine *SysscriptEngine) methodName(
    thread *starlark.Thread,
    b *starlark.Builtin,
    args starlark.Tuple,
    kwargs []starlark.Tuple,
) (starlark.Value, error) {
```
This is the only valid signature — no exceptions.

### UnpackArgs for All Argument Parsing
**Source:** `sysscript.go` lines 222-224, `sys_net_proc.go` lines 103-106, `sys_config.go` lines 16-19
**Apply to:** Every new builtin method
```go
var id string
if err := starlark.UnpackArgs("stats", args, kwargs, "id", &id); err != nil {
    return starlark.None, err
}
// "?" suffix = optional: "namespace?", &ns
```

### Non-Fatal Empty List Return (D-02, D-05)
**Source:** RESEARCH.md Code Examples (derived from existing `log.Printf` + `starlark.NewList` patterns)
**Apply to:** `containers.list()`, `containers.stats()`, `k3s.nodes()`, `k3s.pods()`
```go
if err != nil {
    log.Printf("[containers.list] Docker unavailable: %v", err)
    return starlark.NewList(nil), nil   // non-fatal: return empty list, not error
}
```

### starlarkstruct.FromStringDict for Module Assembly
**Source:** `sysscript.go` lines 159-175 (all sysDict values use this pattern)
**Apply to:** Every new sub-module (`sysContainers`, `sysK3s`) and every item in a returned list where the item has named attributes
```go
starlarkstruct.FromStringDict(starlark.String("typename"), starlark.StringDict{
    "field": starlark.String(value),
})
```

### log.Printf for All Agent Logging
**Source:** `sys_advanced.go` lines 19, 60, 77; `main.go` lines 93, 103, 148
**Apply to:** All new Go files
```go
log.Printf("[subsystem.method] description: %v", err)
// No structured logger; no log levels; just log.Printf
```

### Dict Return for Action Results (success/error)
**Source:** `sys_config.go` lines 28-44
**Apply to:** `containers.stop()`, `containers.start()`, `containers.restart()`, `k3s.apply()`
```go
result := starlark.NewDict(2)
if err != nil {
    result.SetKey(starlark.String("success"), starlark.False)
    result.SetKey(starlark.String("error"), starlark.String(err.Error()))
} else {
    result.SetKey(starlark.String("success"), starlark.True)
    result.SetKey(starlark.String("error"), starlark.String(""))
}
return result, nil
```

### Telemetry "try and assign if no error" Pattern
**Source:** `telemetry.go` lines 68-74, 78-84, 87-95
**Apply to:** Docker and k3s sections in `gatherTelemetry()`
```go
hInfo, err := host.Info()
if err == nil {
    payload.Host = HostInfo{ Hostname: hInfo.Hostname, /* ... */ }
}
// errors are silently skipped — availability is best-effort
```

---

## No Analog Found

No files are fully without analog. However, two files require patterns not present in the codebase:

| File | Role | Data Flow | Missing Pattern | Use Instead |
|---|---|---|---|---|
| `docker_client.go` | utility | request-response | Unix socket `http.Transport` | RESEARCH.md Pattern 2 (verified against Go stdlib) |
| `k3s_client.go` | utility | request-response | kubeconfig YAML parsing + TLS cert loading | RESEARCH.md Pattern 4 + Pitfall 3 (base64 decode required) |

---

## Metadata

**Analog search scope:** `/Users/ryan/development/systemapi.io/systemapi-agent/` (all `.go` files)
**Files scanned:** `sysscript.go`, `sys_advanced.go`, `sys_net_proc.go`, `sys_config.go`, `telemetry.go`, `software.go`, `main.go`, `go.mod`
**Pattern extraction date:** 2026-05-04
