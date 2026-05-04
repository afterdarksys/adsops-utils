# adsops-utils Toolkit Overhaul

## What This Is

adsops-utils is After Dark Systems' internal ops toolkit — a collection of Go CLI tools (hostctl, infractl, statsagent, cloudtop), Python scripts, and deployment artifacts for managing baremetal hosts, Docker containers, k3s clusters, and cloud resources. This overhaul unifies the toolkit around shared data contracts (Protocol Buffers), makes Python3 a first-class citizen alongside Go, integrates with the systemapi-agent's Starlark/Sysscript execution engine, and completes the deployment artifact story for all tools.

## Core Value

Every component — Go tool, Python script, Sysscript, deployed agent — shares the same data contracts and can be operated from a single coherent CLI surface.

## Requirements

### Validated

- [x] hostctl: SSH config import with Docker/k3s probe
- [x] infractl: remote Docker management over SSH
- [x] infractl: remote k3s management over SSH
- [x] statsagent: Prometheus + JSON metrics daemon (host, Docker, k3s)
- [x] statsagent: systemd install, k3s DaemonSet manifest, Dockerfile
- [x] cloudtop: multi-cloud resource monitor

### Active

- [x] Proto data contracts: shared .proto definitions for TelemetryPayload, HostRecord, ContainerStats, K3sStats, StatsSnapshot — Validated in Phase 1
- [x] Go bindings generated from protos (consumed by statsagent, future API) — Validated in Phase 1
- [x] Python3 bindings generated from protos — Validated in Phase 1
- [x] Python3 package (tools/adsops/) with CLI parity: hostctl, infractl, stats modules — Validated in Phase 2
- [x] Python3 sysscript test harness: mock sys module for local .star testing — Validated in Phase 2
- [ ] systemapi-agent: real sys.containers (Docker socket, not stub)
- [ ] systemapi-agent: sys.k3s module (Kubernetes API)
- [ ] systemapi-agent: telemetry includes Docker container stats + k3s state
- [ ] Sysscript shared library: sysscripts/lib/ with common helpers
- [ ] Sysscript per-service scripts: sysscripts/services/{name}/ for each product
- [ ] Hierarchical inventory model: hosts → containers → pods
- [ ] Dockerfiles for all tools (hostctl, infractl)
- [ ] k3s DaemonSet manifests for systemapi-agent
- [ ] docker-compose full local dev stack

### Out of Scope

- Public PyPI release — internal tooling only; no release pipeline needed
- Shared proto repo — this repo owns and generates all protos
- New database migrations — inventory model change is additive/metadata only
- Windows support — Rocky Linux, Debian, Ubuntu targets only

## Context

### Ecosystem
- **systemapi-agent** (`/Users/ryan/development/systemapi.io/systemapi-agent`): separate Go repo, connects to systemapi.io via WebSocket, executes Sysscript (Starlark), sends telemetry every 5s. `sys.containers` and `sys.k3s` are stubs. Changes go directly to that repo as part of this overhaul.
- **Sysscript**: Starlark-based sandboxed scripting (same language as Bazel). Python-like syntax. Services ship `.star` files describing their own health/stats checks.
- **Data formats in use**: YAML (k8s manifests), JSON (tickets, config, inventory), Prometheus text (metrics). Protocol Buffers are the missing contract layer.
- **Host model**: SSH config (`~/.ssh/config`) is the source of truth for primary baremetal hosts. Docker containers and k3s pods are discovered from those hosts and modeled as children.

### Existing Tools
| Tool | Language | Purpose |
|------|----------|---------|
| hostctl | Go | Host inventory (SQLite), SSH config import, probe |
| infractl | Go | Remote Docker + k3s management over SSH |
| statsagent | Go | Metrics daemon: Prometheus + JSON, systemd/Docker/k3s |
| cloudtop | Go | Multi-cloud resource monitor (OCI, CF, Neon, GPU) |
| blackout | Go | Separate tool with its own SQLite schema |
| scripts/python/ | Python | OCI ops scripts (bastion, patching, secrets) |
| scripts/aftercloud/ | Python | OCI VM/container management scripts |

### Python State
Python is currently scattered standalone scripts with no package structure, no pyproject.toml, no shared library. The overhaul introduces `tools/adsops/` as a proper Python package.

## Constraints

- **Languages**: Go (primary), Python3 (first-class), Starlark (.star), YAML, JSON, Protocol Buffers
- **Database**: PostgreSQL (golang-migrate), SQLite (blackout, hostctl)
- **Targets**: Rocky Linux, Debian, Ubuntu baremetal + Docker + k3s
- **Agent repo**: systemapi-agent changes are a deliverable of this overhaul but live in a separate git repo
- **No public release**: Python package is internal; no PyPI, no public container registry requirements

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Protos live in adsops-utils | Single source of truth; systemapi-agent imports generated Go package | ✓ Decided |
| Python CLI parity with Go tools | hostctl/infractl/stats as importable Python library + CLI | ✓ Decided |
| Agent changes in-scope | sys.containers + sys.k3s stubs block sysscript ecosystem value | ✓ Decided |
| Sysscript: lib + per-service | sysscripts/lib/ shared helpers + sysscripts/services/{name}/ | ✓ Decided |
| Inventory: hierarchical | hosts → containers → pods, not flat tags | ✓ Decided |
| YOLO execution | Autonomous phase execution, per-phase branches | ✓ Decided |

---
*Last updated: 2026-05-04 — Phase 1 complete (proto data contracts)*
