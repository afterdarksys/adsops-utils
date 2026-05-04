# Requirements: adsops-utils Toolkit Overhaul

**Defined:** 2026-05-04
**Core Value:** Every component shares the same data contracts and can be operated from a single coherent CLI surface.

## v1 Requirements

### Proto Data Contracts

- [ ] **PROTO-01**: `proto/` directory with buf toolchain (`buf.yaml`, `buf.gen.yaml`)
- [ ] **PROTO-02**: `HostRecord` message — id, hostname, type, provider, region, status, environment, metadata, children
- [ ] **PROTO-03**: `ContainerStats` message — id, name, image, state, cpu_pct, mem_used_bytes, mem_limit_bytes, mem_pct, rx_bps, tx_bps, restart_count
- [ ] **PROTO-04**: `K3sStats` message — node_name, available, total_nodes, ready_nodes, total_pods, running_pods, failed_pods, nodes, namespaces
- [ ] **PROTO-05**: `StatsSnapshot` message — timestamp, host_id, system, disk, network, process, docker, k3s
- [ ] **PROTO-06**: `TelemetryPayload` message — timestamp, host_info, cpu, memory, disk, network, software, docker, k3s (aligned with systemapi-agent)
- [ ] **PROTO-07**: Go bindings generated to `gen/go/adsops/v1/`
- [ ] **PROTO-08**: Python bindings generated to `gen/python/adsops/v1/`

### Python3 Package

- [ ] **PY-01**: `tools/adsops/` with `pyproject.toml`, `src/adsops/` layout, `pip install -e .` works
- [ ] **PY-02**: `adsops.hostctl` module: list, add, update, import-ssh-config with probe
- [ ] **PY-03**: `adsops.infractl` module: docker (ls, start, stop, restart, logs, exec) and k3s (nodes, pods, logs, apply) over SSH
- [ ] **PY-04**: `adsops.stats` module: collect once, fetch from remote statsagent endpoint
- [ ] **PY-05**: `adsops` CLI entry point via Typer: `adsops hostctl`, `adsops infractl`, `adsops stats`
- [ ] **PY-06**: Sysscript test harness: `adsops.sysscript.mock` — Python mock of the Starlark `sys` module for local `.star` unit testing
- [ ] **PY-07**: Proto bindings imported and used for serialization in Python package

### systemapi-agent Improvements

- [ ] **AGENT-01**: `sys.containers.list()` — returns all containers via Docker Unix socket
- [ ] **AGENT-02**: `sys.containers.stats(id)` — returns CPU/mem/net for a container
- [ ] **AGENT-03**: `sys.containers.stop(id)`, `sys.containers.start(id)`, `sys.containers.restart(id)`
- [ ] **AGENT-04**: New `sys.k3s` Starlark module: `nodes()`, `pods(namespace)`, `apply(yaml_str)`
- [ ] **AGENT-05**: `TelemetryPayload` extended with `docker` and `k3s` fields (every 5s telemetry push includes container + cluster state)
- [ ] **AGENT-06**: Telemetry struct types aligned with proto definitions in adsops-utils

### Sysscript Ecosystem

- [ ] **STAR-01**: `sysscripts/lib/host.star` — common host introspection helpers
- [ ] **STAR-02**: `sysscripts/lib/docker.star` — Docker helpers (list containers, get stats)
- [ ] **STAR-03**: `sysscripts/lib/k3s.star` — k3s helpers (list pods, check health)
- [ ] **STAR-04**: `sysscripts/services/statsagent/health.star` — statsagent health check
- [ ] **STAR-05**: `sysscripts/services/changes-api/health.star` — changes API health check
- [ ] **STAR-06**: `sysscripts/services/changes-api/stats.star` — changes API metrics
- [ ] **STAR-07**: Python test harness can execute each `.star` script locally with mock `sys`

### Inventory Overhaul

- [ ] **INV-01**: `HostRecord` supports `children` field: list of `ContainerRecord` and `K3sNodeRecord`
- [ ] **INV-02**: `hostctl list` output shows container/pod children when `--children` flag set
- [ ] **INV-03**: `infractl scan` writes discovered containers/pods back into hostctl inventory as children
- [ ] **INV-04**: Inventory JSON export format matches `HostRecord` proto shape

### Deployment Artifacts

- [ ] **DEPLOY-01**: `deployments/docker/Dockerfile.hostctl` — multi-stage, Alpine final
- [ ] **DEPLOY-02**: `deployments/docker/Dockerfile.infractl` — multi-stage, Alpine final
- [ ] **DEPLOY-03**: `deployments/kubernetes/systemapi-agent-daemonset.yaml` — DaemonSet with hostPID, hostNetwork, Docker socket, k3s kubeconfig mounts
- [ ] **DEPLOY-04**: `docker-compose.yml` updated to include hostctl, infractl, statsagent services
- [ ] **DEPLOY-05**: `deployments/kubernetes/` contains RBAC for systemapi-agent DaemonSet

## v2 Requirements

### Future Enhancements

- Push-based telemetry aggregation endpoint (statsagent → central store)
- gRPC service wrapping the stats collection (proto + Go server)
- Public PyPI release pipeline
- Ansible inventory generation from hostctl (building on existing generate_ansible.py)
- Sysscript marketplace / shared script registry

## Out of Scope

| Feature | Reason |
|---------|--------|
| Public PyPI release | Internal tooling; no versioning/release pipeline needed now |
| Shared proto repo | Adds cross-repo complexity with no current consumer outside these two repos |
| New DB migrations | Inventory hierarchy expressed in metadata JSON, no schema changes needed |
| Windows support | Ops targets are Linux only |
| gRPC server | Proto definitions enable this in v2; not needed for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROTO-01 to PROTO-08 | Phase 1 | Pending |
| PY-01 to PY-07 | Phase 2 | Pending |
| AGENT-01 to AGENT-06 | Phase 3 | Pending |
| STAR-01 to STAR-07 | Phase 4 | Pending |
| INV-01 to INV-04 | Phase 5 | Pending |
| DEPLOY-01 to DEPLOY-05 | Phase 6 | Pending |
