# Phase 1: Proto Data Contracts - Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 8 new files (proto definitions + generated bindings + buf config + Makefile target)
**Analogs found:** 8 / 8 (all from existing Go structs that proto messages must mirror)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `proto/adsops/v1/host_record.proto` | model | request-response | `tools/hostctl/types.go` Resource struct | exact field-set |
| `proto/adsops/v1/container_stats.proto` | model | streaming | `tools/statsagent/collectors/docker.go` ContainerStats + DockerStats | exact field-set |
| `proto/adsops/v1/k3s_stats.proto` | model | streaming | `tools/statsagent/collectors/k3s.go` K3sStats + NodeInfo + NSInfo | exact field-set |
| `proto/adsops/v1/stats_snapshot.proto` | model | streaming | `tools/statsagent/output/json.go` StatsSnapshot | exact field-set |
| `proto/adsops/v1/telemetry_payload.proto` | model | request-response | `/Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go` TelemetryPayload | exact field-set |
| `buf.yaml` | config | — | `tools/statsagent/Makefile` (module naming convention) | partial |
| `buf.gen.yaml` | config | — | root `go.mod` (module path convention) | partial |
| `Makefile` proto targets | config | — | `tools/statsagent/Makefile` + root `Makefile` | role-match |

---

## Pattern Assignments

### `proto/adsops/v1/host_record.proto`

**Analog:** `tools/hostctl/types.go` lines 9–27

**Field preservation — copy ALL fields from Resource struct:**
```go
// Source: tools/hostctl/types.go lines 9-27
type Resource struct {
    ID                 int                    `json:"id"`
    ResourceName       string                 `json:"resource_name"`
    Hostname           string                 `json:"hostname"`
    Type               string                 `json:"type"`
    Provider           string                 `json:"provider"`
    Region             sql.NullString         `json:"region"`           // → optional string in proto
    Status             string                 `json:"status"`
    Environment        string                 `json:"environment"`
    Owners             []string               `json:"owners"`
    MailGroups         []string               `json:"mailgroups"`
    Metadata           map[string]interface{} `json:"metadata"`         // → google.protobuf.Struct
    AverageDailyCost   sql.NullFloat64        `json:"average_daily_cost"`   // → optional double
    AverageMonthlyCost sql.NullFloat64        `json:"average_monthly_cost"` // → optional double
    ExternalID         sql.NullString         `json:"external_id"`      // → optional string
    ExternalURL        sql.NullString         `json:"external_url"`     // → optional string
    CreatedAt          time.Time              `json:"created_at"`       // → google.protobuf.Timestamp
    UpdatedAt          time.Time              `json:"updated_at"`       // → google.protobuf.Timestamp
}
```

**Naming convention:** JSON tags use `snake_case` — proto field names must match exactly to preserve JSON interop. Proto field names are already snake_case by convention, so no transformation needed.

**sql.NullString / sql.NullFloat64 mapping:** These nullable DB types map to proto3 `optional` scalar fields. Use `optional string region = 6;` syntax (proto3 optional, requires `--experimental_allow_proto3_optional` or proto3.15+/buf default).

**Proto message name:** `HostRecord` (not `Resource` — avoids collision with proto reserved concepts and matches the phase goal name).

---

### `proto/adsops/v1/container_stats.proto`

**Analog:** `tools/statsagent/collectors/docker.go` lines 14–35

**Field preservation — DockerStats (top-level wrapper):**
```go
// Source: tools/statsagent/collectors/docker.go lines 14-20
type DockerStats struct {
    Timestamp         time.Time        `json:"timestamp"`        // → google.protobuf.Timestamp
    Available         bool             `json:"available"`
    TotalContainers   int              `json:"total_containers"`
    RunningContainers int              `json:"running_containers"`
    Containers        []ContainerStats `json:"containers"`       // → repeated ContainerStats
}
```

**Field preservation — ContainerStats (per-container):**
```go
// Source: tools/statsagent/collectors/docker.go lines 23-35
type ContainerStats struct {
    ID             string  `json:"id"`
    Name           string  `json:"name"`
    Image          string  `json:"image"`
    State          string  `json:"state"`
    CPUPct         float64 `json:"cpu_pct"`
    MemUsedBytes   int64   `json:"mem_used_bytes"`
    MemLimitBytes  int64   `json:"mem_limit_bytes"`
    MemPct         float64 `json:"mem_pct"`
    RxBytesPerSec  float64 `json:"rx_bytes_per_sec"`
    TxBytesPerSec  float64 `json:"tx_bytes_per_sec"`
    RestartCount   int     `json:"restart_count"`
}
```

**Proto message names:** `DockerStats` (wrapper) and `ContainerStats` (element). The file is named `container_stats.proto` but should define both messages.

**int64 fields:** `mem_used_bytes` and `mem_limit_bytes` are `int64` in Go — use `int64` in proto (not `uint64`; the existing Go code uses signed int64).

---

### `proto/adsops/v1/k3s_stats.proto`

**Analog:** `tools/statsagent/collectors/k3s.go` lines 13–39

**Field preservation — K3sStats:**
```go
// Source: tools/statsagent/collectors/k3s.go lines 13-24
type K3sStats struct {
    Timestamp   time.Time  `json:"timestamp"`    // → google.protobuf.Timestamp
    Available   bool       `json:"available"`
    NodeName    string     `json:"node_name"`
    TotalNodes  int        `json:"total_nodes"`
    ReadyNodes  int        `json:"ready_nodes"`
    TotalPods   int        `json:"total_pods"`
    RunningPods int        `json:"running_pods"`
    FailedPods  int        `json:"failed_pods"`
    Nodes       []NodeInfo `json:"nodes"`        // → repeated NodeInfo
    Namespaces  []NSInfo   `json:"namespaces"`   // → repeated NamespaceInfo
}
```

**Field preservation — NodeInfo:**
```go
// Source: tools/statsagent/collectors/k3s.go lines 27-33
type NodeInfo struct {
    Name    string `json:"name"`
    Role    string `json:"role"`
    Status  string `json:"status"`
    Version string `json:"version"`
}
```

**Field preservation — NSInfo:**
```go
// Source: tools/statsagent/collectors/k3s.go lines 36-39
type NSInfo struct {
    Name        string `json:"name"`
    TotalPods   int    `json:"total_pods"`
    RunningPods int    `json:"running_pods"`
}
```

**Proto message name note:** `NSInfo` is an abbreviation — expand to `NamespaceInfo` in proto for clarity. The generated Go struct name will be `NamespaceInfo`; update the statsagent adapter when consuming generated types.

---

### `proto/adsops/v1/stats_snapshot.proto`

**Analog:** `tools/statsagent/output/json.go` lines 12–21

**Field preservation — StatsSnapshot:**
```go
// Source: tools/statsagent/output/json.go lines 12-21
type StatsSnapshot struct {
    Timestamp time.Time                `json:"timestamp"`          // → google.protobuf.Timestamp
    Context   string                   `json:"context"`            // "host", "docker", "k3s"
    System    *collectors.SystemStats  `json:"system,omitempty"`   // → optional SystemStats
    Disk      *collectors.DiskStats    `json:"disk,omitempty"`     // → optional DiskStats
    Network   *collectors.NetworkStats `json:"network,omitempty"`  // → optional NetworkStats
    Process   *collectors.ProcessStats `json:"process,omitempty"`  // → optional ProcessStats
    Docker    *collectors.DockerStats  `json:"docker,omitempty"`   // → optional DockerStats
    K3s       *collectors.K3sStats     `json:"k3s,omitempty"`      // → optional K3sStats
}
```

**Dependent structs to also define (or import):** StatsSnapshot references SystemStats, DiskStats, NetworkStats, ProcessStats from the collectors package. These are secondary messages needed for the snapshot.

**SystemStats key fields** (from `tools/statsagent/collectors/system.go` lines 14–42):
- `hostname string`, `uptime_seconds double`, `load_avg_1m/5m/15m double`
- CPU: `cpu_used_pct`, `cpu_idle_pct`, `cpu_iowait_pct`, `cpu_cores int32`
- Memory (all int64 bytes): `mem_total_bytes`, `mem_available_bytes`, `mem_used_bytes`, `mem_used_pct double`, `mem_cached_bytes`, `mem_buffers_bytes`
- Swap (all int64 bytes): `swap_total_bytes`, `swap_used_bytes`, `swap_used_pct double`

**DiskStats key fields** (from `tools/statsagent/collectors/disk.go` lines 14–39):
- `MountStats`: `device`, `mount_point`, `fstype string`; `total_bytes`, `used_bytes`, `free_bytes int64`; `used_pct double`
- `IOStats`: `device string`; `reads_per_sec`, `writes_per_sec`, `read_bytes_per_sec`, `write_bytes_per_sec`, `await_ms`, `util_pct double`

**NetworkStats key fields** (from `tools/statsagent/collectors/network.go` lines 13–32):
- `InterfaceStat`: `name string`; `rx_bytes_per_sec`, `tx_bytes_per_sec`, `rx_pkts_per_sec`, `tx_pkts_per_sec double`; `rx_errors`, `tx_errors`, `rx_dropped`, `tx_dropped uint64`; `rx_total_bytes`, `tx_total_bytes uint64`

**ProcessStats key fields** (from `tools/statsagent/collectors/process.go` lines 14–31):
- `total_procs`, `running_procs`, `zombie_procs int32`; `top_cpu`, `top_mem repeated ProcInfo`
- `ProcInfo`: `pid int32`, `name/state string`, `cpu_pct double`, `mem_rss_bytes int64`, `mem_pct double`

**Organize strategy:** Put SystemStats/DiskStats/NetworkStats/ProcessStats in `stats_snapshot.proto` alongside StatsSnapshot, or in separate files and import. Separate files per message group is cleaner and matches the phase goal listing distinct `.proto` files.

---

### `proto/adsops/v1/telemetry_payload.proto`

**Analog:** `/Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go` lines 14–54

**Field preservation — TelemetryPayload:**
```go
// Source: systemapi-agent/telemetry.go lines 14-22
type TelemetryPayload struct {
    Timestamp int64             `json:"timestamp"`           // Unix epoch seconds → use int64 (NOT Timestamp WKT — matches existing wire format)
    Host      HostInfo          `json:"host"`
    CPU       CPUMetrics        `json:"cpu"`
    Memory    MemoryMetrics     `json:"memory"`
    Disk      []DiskMetrics     `json:"disk"`
    Network   NetworkMetrics    `json:"network"`
    Software  []SoftwareMetrics `json:"software,omitempty"` // → repeated SoftwareMetrics
}
```

**IMPORTANT — timestamp type:** The systemapi-agent uses `int64` Unix epoch seconds (`time.Now().Unix()`), NOT `time.Time`. Use `int64 timestamp = 1;` in proto to preserve wire compatibility, not `google.protobuf.Timestamp`.

**Sub-messages:**
```go
// Source: systemapi-agent/telemetry.go lines 24-54
type HostInfo struct {
    Hostname string `json:"hostname"`
    OS       string `json:"os"`
    Platform string `json:"platform"`
    Uptime   uint64 `json:"uptime"`   // → uint64
}
type CPUMetrics struct {
    UsagePercent float64 `json:"usage_percent"`
    Cores        int     `json:"cores"`              // → int32
}
type MemoryMetrics struct {
    Total       uint64  `json:"total"`
    Used        uint64  `json:"used"`
    Free        uint64  `json:"free"`
    UsedPercent float64 `json:"used_percent"`
}
type DiskMetrics struct {
    Path        string  `json:"path"`
    Total       uint64  `json:"total"`
    Used        uint64  `json:"used"`
    Free        uint64  `json:"free"`
    UsedPercent float64 `json:"used_percent"`
}
type NetworkMetrics struct {
    BytesRecv uint64 `json:"bytes_recv"`
    BytesSent uint64 `json:"bytes_sent"`
}
```

**SoftwareMetrics:** Not defined in the read file (defined in a separate file in systemapi-agent). Declare as a minimal message with `string name = 1; string version = 2;` unless the phase scope requires full fidelity — check systemapi-agent for the actual struct if needed.

**uint64 fields:** HostInfo.Uptime, MemoryMetrics.Total/Used/Free, DiskMetrics.Total/Used/Free, NetworkMetrics.BytesRecv/BytesSent are all `uint64` in Go. Use `uint64` in proto.

---

### `buf.yaml`

**No direct analog exists.** Use standard buf v2 layout:

```yaml
# Canonical buf.yaml for a single module at repo root
version: v2
modules:
  - path: proto
    name: buf.build/afterdarksys/adsops-utils  # matches GitHub org in go.mod
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE
```

**Module naming convention** (from `go.mod` line 1): `github.com/afterdarksys/adsops-utils` — org is `afterdarksys`, repo is `adsops-utils`. BSR module name follows the same pattern.

---

### `buf.gen.yaml`

**No direct analog exists.** Generate Go and Python bindings:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/go
    out: gen/go
    opt:
      - paths=source_relative
  - remote: buf.build/protocolbuffers/python
    out: gen/python
    opt:
      - paths=source_relative
  - remote: buf.build/grpc/go          # include if gRPC services are added later
    out: gen/go
    opt:
      - paths=source_relative
```

**Go output path:** `gen/go` — keep generated files outside `tools/` to avoid polluting the per-tool go.mod workspaces.

---

### Makefile proto targets

**Analog:** `tools/statsagent/Makefile` (lines 1–24) + root `Makefile` (lines 1–123)

**Pattern to copy — statsagent Makefile structure:**
```makefile
# Source: tools/statsagent/Makefile lines 1-6
BINARY   := statsagent
VERSION  := 1.0.0
LDFLAGS  := -ldflags="-s -w -X main.version=$(VERSION)"

.PHONY: build build-linux tidy docker clean
```

**Pattern to copy — root Makefile comment header + phony pattern:**
```makefile
# Source: root Makefile lines 1-18
.PHONY: all build clean test lint ...

## target-name: Description (used by help target via sed)
target-name:
	$(GOCMD) ...
```

**New proto targets to add to root Makefile:**
```makefile
## proto-gen: Generate Go and Python bindings from .proto files
proto-gen:
	buf generate

## proto-lint: Lint .proto files
proto-lint:
	buf lint

## proto-breaking: Check for breaking changes
proto-breaking:
	buf breaking --against '.git#branch=main'

## proto-deps: Install buf toolchain
proto-deps:
	go install github.com/bufbuild/buf/cmd/buf@latest
```

---

## Shared Patterns

### JSON tag snake_case convention
**Source:** All struct files in `tools/statsagent/collectors/*.go` and `tools/hostctl/types.go`
**Apply to:** All proto field names (proto uses snake_case natively — this is already aligned)
**Rule:** Proto field names must exactly match the JSON tag values from the Go structs to preserve JSON wire compatibility when using `protojson`. Example: Go `json:"cpu_used_pct"` → proto `float64 cpu_used_pct = N;` → generated Go getter `GetCpuUsedPct()`.

### Timestamp handling — two patterns in use
**Apply to:** All proto messages, carefully per source

| Message | Go type | Proto type | Reason |
|---|---|---|---|
| ContainerStats, K3sStats, StatsSnapshot, SystemStats, DiskStats, NetworkStats | `time.Time` | `google.protobuf.Timestamp` | Rich type, used in statsagent output |
| TelemetryPayload | `int64` (Unix epoch) | `int64` | Existing wire format in systemapi-agent; do not change |

### Go module path
**Source:** `go.mod` line 1, `tools/statsagent/go.mod` line 1
**Apply to:** `buf.gen.yaml` Go output and any `go_package` options in proto files
- Root module: `github.com/afterdarksys/adsops-utils`
- Generated package option: `option go_package = "github.com/afterdarksys/adsops-utils/gen/go/adsops/v1;adsopsv1";`

### int32 vs int64 for count fields
**Source:** All collectors use bare `int` in Go (which is int64 on 64-bit). In proto, count fields (TotalContainers, TotalNodes, CPUCores, etc.) should use `int32` — they will never exceed 2^31. Byte-size fields (MemUsedBytes, MemLimitBytes, etc.) must stay `int64` or `uint64`.

### Build flags pattern
**Source:** `tools/statsagent/Makefile` line 3, root `Makefile` line 17
```makefile
LDFLAGS := -ldflags "-s -w"   # strip debug info for release binaries
```
Proto codegen targets do not need LDFLAGS — they are pure `buf` invocations.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `buf.yaml` | config | — | No existing buf/proto toolchain in codebase |
| `buf.gen.yaml` | config | — | No existing codegen config in codebase |
| `gen/go/adsops/v1/*.pb.go` | generated | — | Output of codegen; not hand-authored |
| `gen/python/adsops/v1/*_pb2.py` | generated | — | Output of codegen; not hand-authored |

---

## Metadata

**Analog search scope:** `tools/statsagent/collectors/`, `tools/statsagent/output/`, `tools/hostctl/`, root `Makefile`, `tools/statsagent/Makefile`, `/Users/ryan/development/systemapi.io/systemapi-agent/`
**Files scanned:** 12
**Pattern extraction date:** 2026-05-03

### Field count summary (proto messages to define)

| Proto message | Field count | Source |
|---|---|---|
| `HostRecord` | 17 fields | `tools/hostctl/types.go` Resource |
| `DockerStats` | 5 fields + repeated | `collectors/docker.go` DockerStats |
| `ContainerStats` | 11 fields | `collectors/docker.go` ContainerStats |
| `K3sStats` | 10 fields + 2 repeated | `collectors/k3s.go` K3sStats |
| `NodeInfo` | 4 fields | `collectors/k3s.go` NodeInfo |
| `NamespaceInfo` | 3 fields | `collectors/k3s.go` NSInfo |
| `StatsSnapshot` | 8 fields (6 optional sub-messages) | `output/json.go` StatsSnapshot |
| `SystemStats` | 17 fields | `collectors/system.go` SystemStats |
| `DiskStats` | 2 repeated sub-messages | `collectors/disk.go` DiskStats |
| `MountStats` | 7 fields | `collectors/disk.go` MountStats |
| `IOStats` | 7 fields | `collectors/disk.go` IOStats |
| `NetworkStats` | 1 repeated | `collectors/network.go` NetworkStats |
| `InterfaceStat` | 10 fields | `collectors/network.go` InterfaceStat |
| `ProcessStats` | 5 fields + 2 repeated | `collectors/process.go` ProcessStats |
| `ProcInfo` | 6 fields | `collectors/process.go` ProcInfo |
| `TelemetryPayload` | 7 fields | `systemapi-agent/telemetry.go` |
| `HostInfo` | 4 fields | `systemapi-agent/telemetry.go` |
| `CPUMetrics` | 2 fields | `systemapi-agent/telemetry.go` |
| `MemoryMetrics` | 4 fields | `systemapi-agent/telemetry.go` |
| `DiskMetrics` | 5 fields | `systemapi-agent/telemetry.go` |
| `NetworkMetrics` | 2 fields | `systemapi-agent/telemetry.go` |
| `SoftwareMetrics` | 2 fields (min) | `systemapi-agent/` (not fully read) |
