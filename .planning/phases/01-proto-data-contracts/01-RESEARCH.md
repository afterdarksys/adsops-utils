# Phase 1: Proto Data Contracts - Research

**Researched:** 2026-05-03
**Domain:** Protocol Buffers toolchain — buf, Go bindings, Python bindings, multi-module monorepo
**Confidence:** HIGH

---

## Summary

This is an implementation-detail research pass. The high-level toolchain decisions are already locked in `proto-toolchain.md` and `SUMMARY.md` (buf, google-protobuf, managed mode, committed gen/). This document captures the exact field-level struct shapes from the Go source that proto messages must mirror, the verified Go module name, exact buf YAML syntax, BSR remote plugin names, and the multi-module strategy for gen/go/.

The core challenge for this phase is fidelity: proto field names must be chosen to be wire-compatible with both the existing Go JSON output (statsagent) and the systemapi-agent TelemetryPayload shape, while keeping protos language-neutral (no go_package in .proto files). Where the two shapes diverge — notably in field naming conventions and type mismatches — the research documents the gap and recommends a canonical proto field name.

**Primary recommendation:** Define all messages in a single `adsops/v1/` package for v1 (not split across telemetry/host/container sub-packages) to avoid cross-package import complexity in both Go and Python. Promote to sub-packages in v2 if the message count grows.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROTO-01 | `proto/` directory with buf toolchain (`buf.yaml`, `buf.gen.yaml`) | buf v2 YAML syntax documented in Code Examples section |
| PROTO-02 | `HostRecord` message | Field mapping from `hostctl/types.go` `Resource` struct in Struct Shape Catalog |
| PROTO-03 | `ContainerStats` message | Field mapping from `collectors/docker.go` `ContainerStats` struct in Struct Shape Catalog |
| PROTO-04 | `K3sStats` message | Field mapping from `collectors/k3s.go` `K3sStats` struct in Struct Shape Catalog |
| PROTO-05 | `StatsSnapshot` message | Field mapping from `output/json.go` `StatsSnapshot` struct in Struct Shape Catalog |
| PROTO-06 | `TelemetryPayload` message | Field mapping from `systemapi-agent/telemetry.go` in Struct Shape Catalog; divergence notes documented |
| PROTO-07 | Go bindings generated to `gen/go/adsops/v1/` | buf.gen.yaml paths=source_relative produces this layout; go.mod strategy documented |
| PROTO-08 | Python bindings generated to `gen/python/adsops/v1/` | buf.gen.yaml python plugin with paths=source_relative; pyproject.toml pattern documented |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Proto schema definition | Source (`proto/`) | — | Language-neutral; no tier owns it |
| Go binding generation | Build tooling (`buf generate`) | `gen/go/` (committed output) | Consumed by statsagent, systemapi-agent, future tools |
| Python binding generation | Build tooling (`buf generate`) | `gen/python/` (committed output) | Consumed by tools/adsops |
| Go import path management | `buf.gen.yaml` managed mode | `gen/go/go.mod` (Option B, deferred) | managed mode injects go_package at gen time |
| Python package installation | `gen/python/pyproject.toml` | `pip install -e gen/python/` | Editable install for dev; importable without PYTHONPATH hacks |

---

## Q1: Root Go Module Name

[VERIFIED: /Users/ryan/development/adsops-utils/go.mod]

```
module github.com/afterdarksys/adsops-utils
```

Go version in go.mod: `go 1.21`

The module already has `google.golang.org/protobuf v1.34.1` as an indirect dependency (pulled in by gin). This means adding proto-generated Go files will not require a new dependency — just promoting it from indirect to direct.

**Import paths for generated Go will be:**
```go
import adsopsv1 "github.com/afterdarksys/adsops-utils/gen/go/adsops/v1"
```

---

## Q2: Struct Shape Catalog — Exact Field Names and Types

Every proto message field name and type is derived from the Go source. Proto field names follow `snake_case` (buf lint enforces this). JSON tags in the Go structs are already snake_case and serve as the canonical field name reference.

### ContainerStats (PROTO-03)

Source: `tools/statsagent/collectors/docker.go` [VERIFIED]

| Go Field | Go Type | JSON Tag | Proto Field | Proto Type | Notes |
|----------|---------|----------|-------------|------------|-------|
| ID | string | `id` | `id` | string | 12-char short ID |
| Name | string | `name` | `name` | string | |
| Image | string | `image` | `image` | string | |
| State | string | `state` | `state` | string | "running", "exited", etc. |
| CPUPct | float64 | `cpu_pct` | `cpu_pct` | double | |
| MemUsedBytes | int64 | `mem_used_bytes` | `mem_used_bytes` | int64 | |
| MemLimitBytes | int64 | `mem_limit_bytes` | `mem_limit_bytes` | int64 | |
| MemPct | float64 | `mem_pct` | `mem_pct` | double | |
| RxBytesPerSec | float64 | `rx_bytes_per_sec` | `rx_bps` | double | **PROTO-03 spec says `rx_bps`** — shorter alias |
| TxBytesPerSec | float64 | `tx_bytes_per_sec` | `tx_bps` | double | **PROTO-03 spec says `tx_bps`** — shorter alias |
| RestartCount | int | `restart_count` | `restart_count` | int32 | |

`DockerStats` (the wrapper) fields used in `StatsSnapshot`:

| Go Field | Proto Field | Proto Type | Notes |
|----------|-------------|------------|-------|
| Available | `available` | bool | |
| TotalContainers | `total_containers` | int32 | |
| RunningContainers | `running_containers` | int32 | |
| Containers | `containers` | repeated ContainerStats | |

### K3sStats (PROTO-04)

Source: `tools/statsagent/collectors/k3s.go` [VERIFIED]

**K3sStats message:**

| Go Field | Go Type | JSON Tag | Proto Field | Proto Type |
|----------|---------|----------|-------------|------------|
| Available | bool | `available` | `available` | bool |
| NodeName | string | `node_name` | `node_name` | string |
| TotalNodes | int | `total_nodes` | `total_nodes` | int32 |
| ReadyNodes | int | `ready_nodes` | `ready_nodes` | int32 |
| TotalPods | int | `total_pods` | `total_pods` | int32 |
| RunningPods | int | `running_pods` | `running_pods` | int32 |
| FailedPods | int | `failed_pods` | `failed_pods` | int32 |
| Nodes | []NodeInfo | `nodes` | `nodes` | repeated NodeInfo |
| Namespaces | []NSInfo | `namespaces` | `namespaces` | repeated NamespaceInfo |

**NodeInfo message** (proto name: `NodeInfo`):

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Name | `name` | string |
| Role | `role` | string |
| Status | `status` | string |
| Version | `version` | string |

**NSInfo message** (proto name: `NamespaceInfo` — rename for clarity):

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Name | `name` | string |
| TotalPods | `total_pods` | int32 |
| RunningPods | `running_pods` | int32 |

### SystemStats (used in StatsSnapshot.system)

Source: `tools/statsagent/collectors/system.go` [VERIFIED]

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Hostname | `hostname` | string |
| UptimeSeconds | `uptime_seconds` | double |
| LoadAvg1 | `load_avg_1m` | double |
| LoadAvg5 | `load_avg_5m` | double |
| LoadAvg15 | `load_avg_15m` | double |
| CPUUsedPct | `cpu_used_pct` | double |
| CPUIdlePct | `cpu_idle_pct` | double |
| CPUIowaitPct | `cpu_iowait_pct` | double |
| CPUCores | `cpu_cores` | int32 |
| MemTotalBytes | `mem_total_bytes` | int64 |
| MemAvailableBytes | `mem_available_bytes` | int64 |
| MemUsedBytes | `mem_used_bytes` | int64 |
| MemUsedPct | `mem_used_pct` | double |
| MemCachedBytes | `mem_cached_bytes` | int64 |
| MemBuffersBytes | `mem_buffers_bytes` | int64 |
| SwapTotalBytes | `swap_total_bytes` | int64 |
| SwapUsedBytes | `swap_used_bytes` | int64 |
| SwapUsedPct | `swap_used_pct` | double |

### DiskStats (used in StatsSnapshot.disk)

Source: `tools/statsagent/collectors/disk.go` [VERIFIED]

**DiskStats → MountStats message:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Device | `device` | string |
| MountPoint | `mount_point` | string |
| FSType | `fstype` | string |
| TotalBytes | `total_bytes` | int64 |
| UsedBytes | `used_bytes` | int64 |
| FreeBytes | `free_bytes` | int64 |
| UsedPct | `used_pct` | double |

**IOStats message:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Device | `device` | string |
| ReadsPerSec | `reads_per_sec` | double |
| WritesPerSec | `writes_per_sec` | double |
| ReadBytesPerSec | `read_bytes_per_sec` | double |
| WriteBytesPerSec | `write_bytes_per_sec` | double |
| AwaitMs | `await_ms` | double |
| UtilPct | `util_pct` | double |

**DiskStats wrapper:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Mounts | `mounts` | repeated MountStats |
| Devices | `devices` | repeated IOStats |

### NetworkStats (used in StatsSnapshot.network)

Source: `tools/statsagent/collectors/network.go` [VERIFIED]

**InterfaceStat message:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Name | `name` | string |
| RxBytesPerSec | `rx_bytes_per_sec` | double |
| TxBytesPerSec | `tx_bytes_per_sec` | double |
| RxPktsPerSec | `rx_pkts_per_sec` | double |
| TxPktsPerSec | `tx_pkts_per_sec` | double |
| RxErrors | `rx_errors` | uint64 |
| TxErrors | `tx_errors` | uint64 |
| RxDropped | `rx_dropped` | uint64 |
| TxDropped | `tx_dropped` | uint64 |
| RxTotalBytes | `rx_total_bytes` | uint64 |
| TxTotalBytes | `tx_total_bytes` | uint64 |

**NetworkStats wrapper:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Interfaces | `interfaces` | repeated InterfaceStat |

### ProcessStats (used in StatsSnapshot.process)

Source: `tools/statsagent/collectors/process.go` [VERIFIED]

**ProcInfo message:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| PID | `pid` | int32 |
| Name | `name` | string |
| State | `state` | string |
| CPUPct | `cpu_pct` | double |
| MemRSSBytes | `mem_rss_bytes` | int64 |
| MemPct | `mem_pct` | double |

**ProcessStats wrapper:**

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| TotalProcs | `total_procs` | int32 |
| RunningProcs | `running_procs` | int32 |
| ZombieProcs | `zombie_procs` | int32 |
| TopCPU | `top_cpu` | repeated ProcInfo |
| TopMem | `top_mem` | repeated ProcInfo |

### StatsSnapshot (PROTO-05)

Source: `tools/statsagent/output/json.go` [VERIFIED]

| Go Field | Proto Field | Proto Type |
|----------|-------------|------------|
| Timestamp | `timestamp` | google.protobuf.Timestamp |
| Context | `context` | string |
| System | `system` | SystemStats (optional) |
| Disk | `disk` | DiskStats (optional) |
| Network | `network` | NetworkStats (optional) |
| Process | `process` | ProcessStats (optional) |
| Docker | `docker` | DockerStats (optional) |
| K3s | `k3s` | K3sStats (optional) |

Note: All sub-fields are `omitempty` in Go. In proto3, all fields are optional by default and omit when zero-value. No `optional` keyword needed for scalar fields, but using `optional` keyword for message fields makes presence detection explicit. Use `optional` for all message-type fields in StatsSnapshot.

### HostRecord (PROTO-02)

Source: `tools/hostctl/types.go` `Resource` struct [VERIFIED]

The proto `HostRecord` is a simplified view of `Resource` for cross-system use. Not all DB-internal fields (sql.NullString, AverageDailyCost, etc.) need to be in the proto — only fields relevant for inventory export and inter-tool exchange.

| Go Field | Proto Field | Proto Type | Include? |
|----------|-------------|------------|---------|
| ID | `id` | int32 | Yes |
| ResourceName | `resource_name` | string | Yes |
| Hostname | `hostname` | string | Yes |
| Type | `type` | string | Yes |
| Provider | `provider` | string | Yes |
| Region (sql.NullString) | `region` | string | Yes — empty string when null |
| Status | `status` | string | Yes |
| Environment | `environment` | string | Yes |
| Owners | `owners` | repeated string | Yes |
| Metadata | `metadata` | google.protobuf.Struct | Yes — preserves arbitrary JSON |
| ExternalID | `external_id` | string | Yes |
| ExternalURL | `external_url` | string | Yes |
| CreatedAt | `created_at` | google.protobuf.Timestamp | Yes |
| UpdatedAt | `updated_at` | google.protobuf.Timestamp | Yes |
| — | `children` | repeated HostRecord | Yes — NEW for PROTO-02/INV-01 |

Fields omitted from proto: `MailGroups`, `AverageDailyCost`, `AverageMonthlyCost` — internal DB fields not needed by other tools. Add if needed in v2.

### TelemetryPayload (PROTO-06)

Source: `systemapi-agent/telemetry.go` [VERIFIED]

This is where the two repos diverge. The existing `TelemetryPayload` in systemapi-agent uses different field naming and types than statsagent's `StatsSnapshot`. The proto must serve as the bridge — AGENT-06 requires aligning the agent's telemetry struct with proto definitions.

**Divergence table:**

| Concept | systemapi-agent field | statsagent equivalent | Proto field | Resolution |
|---------|-----------------------|-----------------------|-------------|-----------|
| Timestamp | `timestamp` (int64 unix) | `timestamp` (time.Time) | `timestamp` (Timestamp) | Use google.protobuf.Timestamp; both repos convert |
| Host info | `host` (HostInfo) | `system.hostname` + `system.uptime_seconds` | `host_info` (HostInfo msg) | Keep agent's HostInfo shape; statsagent embeds hostname in SystemStats |
| CPU | `cpu` (CPUMetrics: usage_percent, cores) | `system` (SystemStats: cpu_used_pct, cpu_cores, idle, iowait) | `cpu` (CPUInfo) | Proto uses statsagent's richer shape; agent AGENT-06 extends to match |
| Memory | `memory` (MemoryMetrics: total, used, free, used_percent) | `system` (same 4 fields + cached, buffers, swap) | `memory` (MemoryInfo) | Proto uses statsagent shape; agent fields are a subset |
| Disk | `disk` ([]DiskMetrics: path, total, used, free, used_pct) | `disk.mounts` (MountStats: same + device, fstype, io) | `disk` (DiskInfo with mounts + devices) | Use statsagent shape; agent is a subset |
| Network | `network` (bytes_recv, bytes_sent — scalars) | `network.interfaces` ([]InterfaceStat — per-NIC) | `network` (NetworkInfo with interfaces) | Use statsagent shape; agent currently aggregates all NICs |
| Software | `software` ([]SoftwareMetrics) | not collected | `software` (repeated SoftwareInfo) | Keep; statsagent doesn't collect this |
| Docker | not in current agent payload | `docker` (DockerStats) | `docker` (DockerStats) | AGENT-05: agent gains this field |
| K3s | not in current agent payload | `k3s` (K3sStats) | `k3s` (K3sStats) | AGENT-05: agent gains this field |

**TelemetryPayload proto message fields:**

| Proto Field | Proto Type | Notes |
|-------------|------------|-------|
| `timestamp` | google.protobuf.Timestamp | |
| `host_id` | string | host identifier (agent config) |
| `host_info` | HostInfo | hostname, os, platform, uptime_seconds |
| `cpu` | SystemStats | reuse SystemStats (superset of agent's CPUMetrics) |
| `memory` | SystemStats | embedded in SystemStats; or split — see note |
| `disk` | DiskStats | |
| `network` | NetworkStats | |
| `software` | repeated SoftwareInfo | agent-only; statsagent doesn't collect |
| `docker` | DockerStats | AGENT-05 extension |
| `k3s` | K3sStats | AGENT-05 extension |

**Design decision for cpu/memory:** Rather than embedding SystemStats (which conflates CPU, memory, swap, load, uptime), define separate `CpuInfo` and `MemoryInfo` messages that hold the statsagent SystemStats fields split by concern. This aligns with TelemetryPayload's existing `cpu` and `memory` top-level keys while preserving richer statsagent data. [ASSUMED — both designs are valid; recommend raising with user before locking field numbers]

**SoftwareInfo message** (from systemapi-agent, not in statsagent):
Fields unknown — `gatherSoftware()` not read in this research pass. [ASSUMED — likely: name string, version string, package_manager string based on common patterns]

---

## Q3: buf.yaml v2 Minimal Config

[CITED: https://buf.build/docs/configuration/v2/buf-yaml/]

```yaml
version: v2
modules:
  - path: proto
    name: buf.build/afterdarksys/adsops  # optional: only needed for BSR push
lint:
  use:
    - DEFAULT
breaking:
  use:
    - FILE
```

**Key points:**
- `version: v2` is required — v1 syntax is deprecated
- `modules[].path` points to the directory containing `.proto` files
- `name` is optional unless pushing to BSR; omit for local-only use
- `lint.use: [DEFAULT]` enforces standard rules including `FIELD_NAMES_LOWER_SNAKE_CASE`, `ENUM_ZERO_VALUE_SUFFIX`, `PACKAGE_VERSION_SUFFIX`
- `breaking.use: [FILE]` detects wire-incompatible changes (field number changes, type changes, removal)
- Place `buf.yaml` inside the `proto/` directory (co-located with `.proto` files), NOT at repo root

---

## Q4: buf.gen.yaml v2 — Exact Plugin Names

[CITED: https://buf.build/docs/configuration/v2/buf-gen-yaml/]
[VERIFIED: BSR plugin registry confirmed via prior research in proto-toolchain.md]

```yaml
version: v2
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: github.com/afterdarksys/adsops-utils/gen/go
plugins:
  # Go message bindings (protoc-gen-go)
  - remote: buf.build/protocolbuffers/go:v1.34.2
    out: gen/go
    opt:
      - paths=source_relative

  # Python message bindings (_pb2.py)
  - remote: buf.build/protocolbuffers/python:v25.3
    out: gen/python
    opt:
      - paths=source_relative

  # Python type stubs (_pb2.pyi) for mypy and IDE completion
  - remote: buf.build/protocolbuffers/pyi:v25.3
    out: gen/python
    opt:
      - paths=source_relative

inputs:
  - directory: proto
```

**Place at repo root** (not inside proto/).

**Plugin names verified:**
- `buf.build/protocolbuffers/go` — official BSR plugin for protoc-gen-go [CITED: buf.build/protocolbuffers/go]
- `buf.build/protocolbuffers/python` — official BSR plugin for _pb2.py generation [CITED: buf.build/protocolbuffers/python]
- `buf.build/protocolbuffers/pyi` — official BSR plugin for .pyi stub generation [CITED: buf.build/protocolbuffers/pyi]

**NOT included (per scope):**
- `buf.build/grpc/go` — gRPC service stubs; v2 scope only
- `buf.build/grpc/python` — gRPC Python; v2 scope only; also has known incompatibility with grpc_tools
- `judahrand/python-betterproto` — explicitly ruled out

**Version pinning note:** The version suffixes (`:v1.34.2`, `:v25.3`) are optional but recommended for reproducibility. Without a version pin, buf uses the latest available plugin version. Omit pins if always-latest is acceptable; add them after the first working generation for stability. [ASSUMED — pin or not-pin is a team preference; either is correct]

**managed mode note:** `go_package_prefix` injects the Go import path prefix at generation time. This means `.proto` files must NOT contain `option go_package = "..."`. If any proto file has this option, buf managed mode will override it (or error, depending on version). For new protos written in this phase, simply omit `option go_package`.

---

## Q5: gen/ Directory Location in Multi-Module Repo

[CITED: https://go.dev/ref/mod — Go Modules Reference]
[CITED: proto-toolchain.md Option A / Option B analysis]

**For Phase 1 (development, pre-CI):** gen/go/ lives under the root module (`github.com/afterdarksys/adsops-utils`) — NO separate go.mod in gen/go/.

Layout:
```
adsops-utils/
  go.mod          # module github.com/afterdarksys/adsops-utils
  gen/
    go/
      adsops/
        v1/
          *.pb.go  # generated — part of root module
    python/
      adsops/
        v1/
          *_pb2.py
          *_pb2.pyi
      pyproject.toml
  proto/
    buf.yaml
    adsops/
      v1/
        *.proto
  buf.gen.yaml
```

With this layout, systemapi-agent uses a `replace` directive pointing at the adsops-utils root:

```
require github.com/afterdarksys/adsops-utils v0.0.0-00010101000000-000000000000

replace github.com/afterdarksys/adsops-utils => /path/to/local/adsops-utils
```

**For Phase 3+ (before systemapi-agent CI/CD):** Promote to separate module by adding `gen/go/go.mod`:

```
module github.com/afterdarksys/adsops-utils/gen/go

go 1.21

require google.golang.org/protobuf v1.34.1
```

Then systemapi-agent's go.mod changes to:
```
require github.com/afterdarksys/adsops-utils/gen/go v0.1.0

replace github.com/afterdarksys/adsops-utils/gen/go => /path/to/local/adsops-utils/gen/go
```

Git tags for this separate module use the path prefix: `gen/go/v0.1.0`

**Phase 1 decision: do NOT create gen/go/go.mod yet.** Keep generated files as part of the root module. The separate module is a Phase 3 pre-condition, documented in SUMMARY.md research flags.

---

## Q6: go.mod replace Directive Syntax

[CITED: https://go.dev/ref/mod#go-mod-file-replace]
[VERIFIED: go.mod format confirmed via Go Modules Reference]

For systemapi-agent's go.mod pointing at adsops-utils gen/ locally during Phase 1 (root module approach):

```
module github.com/systemapi.io/systemapi-agent

go 1.21

require (
    github.com/afterdarksys/adsops-utils v0.0.0-00010101000000-000000000000
)

replace github.com/afterdarksys/adsops-utils => ../adsops-utils
```

The pseudo-version `v0.0.0-00010101000000-000000000000` is the conventional placeholder used with `replace` when no real version exists. Use a relative path (`../adsops-utils`) if repos are siblings; use absolute path if not. `go mod tidy` will rewrite the pseudo-version after the replace is added.

**Shorter form that also works:**
```
replace github.com/afterdarksys/adsops-utils v0.0.0 => ../adsops-utils
```
Both forms are valid. The full pseudo-version form is what `go mod tidy` generates automatically.

**If using the separate gen/go module (Phase 3+):**
```
replace github.com/afterdarksys/adsops-utils/gen/go => ../adsops-utils/gen/go
```

---

## Standard Stack

### Core
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| buf CLI | latest | Proto generation, lint, breaking detection | [VERIFIED: brew install bufbuild/buf/buf] |
| google.golang.org/protobuf | v1.34.1 | Go proto runtime (already in go.mod indirect) | [VERIFIED: go.mod] |
| protobuf (Python) | >=5.26.0 | Python proto runtime | [CITED: proto-toolchain.md] |
| mypy-protobuf | >=3.6.0 | Python type stubs (dev) | [CITED: proto-toolchain.md] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google.golang.org/protobuf/types/known/timestamppb | (bundled) | Timestamp message type | All messages with time fields |
| google.golang.org/protobuf/types/known/structpb | (bundled) | Struct/JSON message type | HostRecord.metadata |

### Installation

```bash
# buf CLI (macOS)
brew install bufbuild/buf/buf

# Verify
buf --version

# Python runtime (add to gen/python/pyproject.toml and tools/adsops/pyproject.toml)
pip install "protobuf>=5.26.0"

# Python stubs (dev only)
pip install "mypy-protobuf>=3.6.0"

# Generate bindings
cd /path/to/adsops-utils
buf generate
```

Go: no `go get` needed for protobuf runtime — already in go.mod. After generation, run `go mod tidy` to promote `google.golang.org/protobuf` from indirect to direct.

---

## Architecture Patterns

### Recommended Project Structure

```
adsops-utils/
  buf.gen.yaml              # generation config (root)
  proto/
    buf.yaml                # module config (inside proto/)
    adsops/
      v1/
        host.proto          # HostRecord
        stats.proto         # StatsSnapshot, SystemStats, DiskStats, NetworkStats, ProcessStats
        container.proto     # ContainerStats, DockerStats, K3sStats, NodeInfo, NamespaceInfo
        telemetry.proto     # TelemetryPayload, HostInfo, SoftwareInfo
  gen/
    go/
      adsops/
        v1/
          host.pb.go
          stats.pb.go
          container.pb.go
          telemetry.pb.go
    python/
      adsops/
        v1/
          host_pb2.py  host_pb2.pyi
          stats_pb2.py  stats_pb2.pyi
          container_pb2.py  container_pb2.pyi
          telemetry_pb2.py  telemetry_pb2.pyi
      pyproject.toml
  Makefile                  # proto, proto-lint, proto-breaking targets
```

**Single package `adsops/v1/` rationale:** The REQUIREMENTS split (telemetry/v1, host/v1, container/v1) in the prior research adds cross-package imports for every message that references another domain. For v1, all messages fit comfortably in a single package. Split at v2 if the package exceeds ~15 messages or if different teams own different domains. [ASSUMED — single-package is a recommendation; user may prefer the split; call out in plan]

### Pattern: google.protobuf.Timestamp for all time fields

```protobuf
// Source: https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp
import "google/protobuf/timestamp.proto";

message StatsSnapshot {
  google.protobuf.Timestamp timestamp = 1;
  // ...
}
```

Go usage:
```go
import "google.golang.org/protobuf/types/known/timestamppb"

snap := &adsopsv1.StatsSnapshot{
    Timestamp: timestamppb.New(time.Now()),
}
// Convert back:
t := snap.Timestamp.AsTime()
```

Python usage:
```python
from google.protobuf.timestamp_pb2 import Timestamp
from adsops.v1.stats_pb2 import StatsSnapshot
import time

snap = StatsSnapshot()
snap.timestamp.FromDatetime(datetime.utcnow())
```

### Pattern: google.protobuf.Struct for HostRecord.metadata

```protobuf
import "google/protobuf/struct.proto";

message HostRecord {
  // ...
  google.protobuf.Struct metadata = 9;
}
```

Go usage:
```go
import "google.golang.org/protobuf/types/known/structpb"

m, _ := structpb.NewStruct(map[string]interface{}{
    "children": []interface{}{},
    "_last_scan": "2026-05-03T00:00:00Z",
})
record.Metadata = m
```

### Anti-Patterns to Avoid

- **Using `int64` for timestamps:** Use `google.protobuf.Timestamp`. The systemapi-agent currently uses `int64` unix seconds — AGENT-06 must migrate this.
- **Putting `option go_package` in .proto files:** buf managed mode handles this. Adding it manually will conflict.
- **Using `json_name` field options to alias field names:** Keep JSON names matching proto field names (already snake_case). This avoids confusion when the Go struct JSON tags differ from proto field names.
- **Splitting gen/ into a separate go.mod for Phase 1:** Premature. Creates multi-module complexity before it's needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timestamp serialization | Custom int64/string converters | `google.protobuf.Timestamp` | Timezone-safe, cross-language, handles nanos |
| Arbitrary JSON in proto | Custom string field + json.Marshal | `google.protobuf.Struct` | Native proto support, works in Python too |
| Proto generation | Makefile + protoc + shell flags | `buf generate` | Reproducible, no local plugin installs, lint built-in |
| Breaking change detection | Manual diff or changelog review | `buf breaking` | Wire-level check, catches field number reuse |
| Python import path setup | sys.path manipulation | `pip install -e gen/python/` | Standard editable install, works in venvs |

---

## Common Pitfalls

### Pitfall 1: Field number reuse after deletion
**What goes wrong:** A proto field is deleted, its number is reused by a new field with a different type. Old serialized data decodes with wrong type.
**Why it happens:** Proto field numbers are permanent identifiers. Deleting a field does not retire its number.
**How to avoid:** Use `reserved` statement when deleting fields: `reserved 5; reserved "old_field_name";`
**Warning signs:** `buf breaking` will catch attempted reuse.

### Pitfall 2: paths=source_relative omitted for Go
**What goes wrong:** Generated .pb.go files land in `gen/go/github.com/afterdarksys/adsops-utils/proto/adsops/v1/` instead of `gen/go/adsops/v1/`.
**Why it happens:** Without `paths=source_relative`, protoc-gen-go uses the full Go import path as the output directory.
**How to avoid:** Always include `opt: [paths=source_relative]` in buf.gen.yaml for the Go plugin.

### Pitfall 3: buf.yaml placed at repo root instead of inside proto/
**What goes wrong:** buf lint and buf generate include Go source files, Makefiles, etc. in the "module", producing spurious errors.
**Why it happens:** buf v2 uses `modules[].path` to define which directory contains proto files. If buf.yaml is at root without a `modules` section, it treats the entire repo as proto source.
**How to avoid:** Place buf.yaml inside `proto/` (or specify `modules: [{path: proto}]` in a root-level buf.yaml). The buf.gen.yaml `inputs: [{directory: proto}]` also scopes generation correctly.

### Pitfall 4: google.protobuf.Timestamp import path
**What goes wrong:** `import "google/protobuf/timestamp.proto"` fails with "file not found".
**Why it happens:** buf needs Well-Known Types (WKT) to be available. In buf v2 with BSR remote plugins, WKTs are automatically available — no extra dependency needed.
**How to avoid:** Use BSR remote plugins (not local protoc). WKTs are bundled in the BSR plugin environment.

### Pitfall 5: Python _pb2 import path confusion
**What goes wrong:** `from adsops.v1.stats_pb2 import StatsSnapshot` fails with ModuleNotFoundError.
**Why it happens:** `gen/python/` is not on PYTHONPATH, or the `adsops/v1/` directories are missing `__init__.py` files.
**How to avoid:** Use `pip install -e gen/python/` with a pyproject.toml that declares `adsops` as the package. The `__init__.py` files in generated output — note that protoc does NOT generate `__init__.py` files; they must be created manually or via a post-generation script.

---

## Code Examples

### Minimal proto file (adsops/v1/container.proto)

```protobuf
// Source: buf.build docs + field mapping from docker.go
syntax = "proto3";

package adsops.v1;

// No option go_package — managed mode injects this at generation time.

message ContainerStats {
  string id = 1;
  string name = 2;
  string image = 3;
  string state = 4;
  double cpu_pct = 5;
  int64 mem_used_bytes = 6;
  int64 mem_limit_bytes = 7;
  double mem_pct = 8;
  double rx_bps = 9;
  double tx_bps = 10;
  int32 restart_count = 11;
}

message DockerStats {
  bool available = 1;
  int32 total_containers = 2;
  int32 running_containers = 3;
  repeated ContainerStats containers = 4;
}
```

### Post-generation: create __init__.py files for Python

```bash
# Run after buf generate — protoc does not generate these
find gen/python -type d | while read dir; do
  touch "$dir/__init__.py"
done
```

Add this to the `proto` Makefile target:

```makefile
.PHONY: proto proto-lint proto-breaking

proto:
	buf generate
	find gen/python -type d -exec touch {}/__init__.py \;

proto-lint:
	buf lint proto/

proto-breaking:
	buf breaking proto/ --against '.git#branch=main'
```

### gen/python/pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "adsops-proto"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["protobuf>=5.26"]

[tool.setuptools.packages.find]
where = ["."]
include = ["adsops*"]
```

Install in dev: `pip install -e gen/python/`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Single `adsops/v1/` proto package is preferable to split domain packages | Architecture Patterns | Low — either works; a split requires more cross-package imports but is structurally fine |
| A2 | `cpu` and `memory` should be separate messages in TelemetryPayload rather than reusing SystemStats | Q2 TelemetryPayload | Medium — if SystemStats is reused, the Go conversion in AGENT-06 is simpler; if split, TelemetryPayload has a cleaner public shape |
| A3 | BSR plugin version pins (`:v1.34.2`, `:v25.3`) are optional for this project | Q4 buf.gen.yaml | Low — unpinned will use latest; introduces potential surprise upgrades |
| A4 | `SoftwareInfo` message fields (name, version, package_manager) | Q2 TelemetryPayload | Low for Phase 1 — SoftwareInfo is systemapi-agent only; gatherSoftware() not read; can be defined as `bytes raw_json = 1` placeholder and fleshed out in Phase 3 |
| A5 | `__init__.py` files must be created manually after buf generate | Code Examples | High if wrong — Python package will not be importable without them; verify with a `buf generate` test run |

---

## Open Questions

1. **Single package vs. split domain packages for proto/**
   - What we know: Either works structurally; single package is simpler for v1
   - What's unclear: Whether Ryan wants proto/ to mirror the domain split in REQUIREMENTS.md (`telemetry/v1`, `host/v1`, `container/v1`)
   - Recommendation: Default to single `adsops/v1/` in the plan; note the alternative in a comment

2. **SoftwareInfo message shape**
   - What we know: systemapi-agent has `SoftwareMetrics` type; `gatherSoftware()` function not read
   - What's unclear: Exact fields (name, version, path, package manager, etc.)
   - Recommendation: Define as a placeholder with `string name = 1; string version = 2;` in Phase 1; flesh out in Phase 3 when systemapi-agent work begins

3. **protobuf v1.34.1 (in go.mod) vs buf plugin v1.34.2**
   - What we know: `google.golang.org/protobuf v1.34.1` is in go.mod; BSR plugin defaults to v1.34.2
   - What's unclear: Whether generated code from v1.34.2 plugin is compatible with v1.34.1 runtime
   - Recommendation: Run `go get google.golang.org/protobuf@v1.34.2` as part of Phase 1 to align; patch versions are always backward compatible

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| buf CLI | PROTO-01 generation | No | — | Install via brew: `brew install bufbuild/buf/buf` |
| Go | PROTO-07 go build verify | Yes | go1.25.7 | — |
| Python 3 | PROTO-08 import verify | [ASSUMED: yes] | — | — |
| pip | gen/python install | [ASSUMED: yes] | — | — |
| git | buf breaking detection | Yes (repo is git) | — | — |

**Missing dependencies blocking execution:**
- `buf` is not installed. Wave 0 task must install it before generation can run.

---

## Validation Architecture

**Note:** `workflow.nyquist_validation` is not set in config.json (key absent) — treat as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Go: `go test ./...` (no extra framework); Python: none detected yet |
| Config file | none — standard Go test tooling |
| Quick run command | `go build ./gen/go/...` (compilation is the test for generated Go) |
| Full suite command | `go test ./...` (root module) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROTO-01 | buf.yaml + buf.gen.yaml present and valid | smoke | `buf lint proto/` | No — Wave 0 |
| PROTO-02 | HostRecord compiles in Go | compile | `go build ./gen/go/...` | No — Wave 0 |
| PROTO-03 | ContainerStats compiles in Go | compile | `go build ./gen/go/...` | No — Wave 0 |
| PROTO-04 | K3sStats compiles in Go | compile | `go build ./gen/go/...` | No — Wave 0 |
| PROTO-05 | StatsSnapshot compiles in Go | compile | `go build ./gen/go/...` | No — Wave 0 |
| PROTO-06 | TelemetryPayload compiles in Go | compile | `go build ./gen/go/...` | No — Wave 0 |
| PROTO-07 | gen/go/ files present after buf generate | smoke | `ls gen/go/adsops/v1/*.pb.go` | No — Wave 0 |
| PROTO-08 | gen/python/ importable after pip install | smoke | `python -c "from adsops.v1.stats_pb2 import StatsSnapshot"` | No — Wave 0 |

### Wave 0 Gaps
- [ ] Install buf: `brew install bufbuild/buf/buf`
- [ ] `proto/buf.yaml` — PROTO-01
- [ ] `buf.gen.yaml` — PROTO-01
- [ ] `proto/adsops/v1/*.proto` — PROTO-02 through PROTO-06
- [ ] `gen/python/pyproject.toml` — PROTO-08
- [ ] `Makefile` proto targets — PROTO-01

---

## Security Domain

This phase defines data schemas and generation tooling only. No authentication, session management, access control, cryptography, or input validation is involved. ASVS categories V2, V3, V4, V6 do not apply.

**V5 (Input Validation):** Proto deserialization validates field types by definition — proto3 silently ignores unknown fields on decode and uses zero values for missing fields. No additional validation layer needed at this layer; validation of proto-decoded values belongs in Phase 2 (Python package) and Phase 3 (agent).

---

## Sources

### Primary (HIGH confidence)
- `/Users/ryan/development/adsops-utils/go.mod` — module name, Go version, existing protobuf dependency
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/docker.go` — ContainerStats, DockerStats exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/k3s.go` — K3sStats, NodeInfo, NSInfo exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/system.go` — SystemStats exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/disk.go` — DiskStats, MountStats, IOStats exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/network.go` — NetworkStats, InterfaceStat exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/collectors/process.go` — ProcessStats, ProcInfo exact fields
- `/Users/ryan/development/adsops-utils/tools/statsagent/output/json.go` — StatsSnapshot structure
- `/Users/ryan/development/adsops-utils/tools/hostctl/types.go` — Resource struct (HostRecord basis)
- `/Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go` — TelemetryPayload, CPUMetrics, MemoryMetrics, DiskMetrics, NetworkMetrics
- `.planning/research/proto-toolchain.md` — buf.yaml/buf.gen.yaml patterns, plugin names, Python runtime decision
- `.planning/research/SUMMARY.md` — locked decisions, phase ordering rationale
- [Go Modules Reference](https://go.dev/ref/mod) — replace directive syntax

### Secondary (MEDIUM confidence)
- [buf.build/docs/configuration/v2/buf-gen-yaml/](https://buf.build/docs/configuration/v2/buf-gen-yaml/) — YAML structure confirmed via prior research
- [buf.build/docs/configuration/v2/buf-yaml/](https://buf.build/docs/configuration/v2/buf-yaml/) — module config confirmed via prior research

---

## Metadata

**Confidence breakdown:**
- Struct field catalog: HIGH — read directly from source files
- buf YAML syntax: HIGH — cited from prior verified research
- BSR plugin names: HIGH — cited from prior verified research
- Module/replace strategy: HIGH — cited from Go Modules Reference
- Python __init__.py requirement: MEDIUM — standard protoc behavior but not run in this session to confirm
- SoftwareInfo message shape: LOW — source file not read

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (buf BSR plugin versions may change; Go and Python runtime versions stable)
