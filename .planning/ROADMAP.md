# Roadmap: adsops-utils Toolkit Overhaul

## Overview

This overhaul builds a unified ops toolkit by establishing proto data contracts first, then layering Go and Python tooling on top of them, improving the systemapi-agent's Starlark runtime, building a sysscript library, extending the inventory hierarchy, and finally producing deployment-ready artifacts for all tools. Phases 1-3 are strictly sequential (each depends on the previous); Phases 4, 5, and 6 unlock after Phase 3 completes, with 5 and 6 largely parallel.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Proto Data Contracts** - buf toolchain + .proto definitions + committed Go/Python bindings
- [ ] **Phase 2: Python3 Package** - tools/adsops/ package with Typer CLI, SSH, MockSys, proto imports
- [ ] **Phase 3: systemapi-agent Improvements** - SEPARATE REPO: real sys.containers, sys.k3s, Thread.Load, extended telemetry
- [ ] **Phase 4: Sysscript Ecosystem** - sysscripts/lib/ helpers + per-service scripts + Python test harness
- [ ] **Phase 5: Inventory Hierarchy** - hierarchical host->container->pod model, hostctl --children, infractl scan writeback
- [ ] **Phase 6: Deployment Artifacts** - Dockerfiles, k3s DaemonSet manifests, docker-compose profiles

## Phase Details

### Phase 1: Proto Data Contracts
**Goal**: A single `buf generate` command produces committed, importable Go and Python bindings from versioned proto definitions
**Depends on**: Nothing (first phase)
**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06, PROTO-07, PROTO-08
**Success Criteria** (what must be TRUE):
  1. `buf generate` runs without errors and produces files under `gen/go/adsops/v1/` and `gen/python/adsops/v1/`
  2. Generated Go bindings compile with `go build ./gen/go/...` and include all five message types (HostRecord, ContainerStats, K3sStats, StatsSnapshot, TelemetryPayload)
  3. Generated Python bindings install via `pip install -e gen/python/` and are importable as `from adsops.v1 import host_pb2`
  4. `make proto-lint` and `make proto-breaking` targets exist and pass
  5. `gen/` directory is committed to the repo (downstream phases can import without buf installed)
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — buf toolchain setup, config files, Makefile targets
- [x] 01-02-PLAN.md — proto definitions (all 5 .proto files)
- [x] 01-03-PLAN.md — code generation, Python packaging, Go/Python verification
**UI hint**: no

### Phase 2: Python3 Package
**Goal**: Users can run `adsops hostctl list`, `adsops infractl docker ls <host>`, and `adsops stats once` from a pip-installed Python package
**Depends on**: Phase 1
**Requirements**: PY-01, PY-02, PY-03, PY-04, PY-05, PY-06, PY-07
**Success Criteria** (what must be TRUE):
  1. `pip install -e tools/adsops/` succeeds and places `adsops` binary on PATH
  2. `adsops hostctl list` returns inventory entries using the same PostgreSQL DB as the Go hostctl binary
  3. `adsops infractl docker ls <host>` executes over SSH via asyncssh and returns container list
  4. `adsops stats once` collects local host metrics and prints output
  5. `MockSys` passes all unit tests without requiring SSH, Docker, or a live agent — test suite runs with `pytest tools/adsops/`
**Plans**: 3 plans
Plans:
- [x] 02-01-PLAN.md — Package scaffolding, config, output utils, hostctl module + tests
- [x] 02-02-PLAN.md — infractl module (asyncssh, Docker, k3s commands) + tests
- [x] 02-03-PLAN.md — stats module, MockSys harness, CLI finalization + tests
**UI hint**: no

### Phase 3: systemapi-agent Improvements
**Goal**: The systemapi-agent (in the separate systemapi-agent repo) sends telemetry that includes live container and k3s data, and can execute sysscripts that use `load()`

**IMPORTANT: This phase commits to `/Users/ryan/development/systemapi.io/systemapi-agent` — a different git repository from adsops-utils. All work in this phase is done in that repo.**

**Depends on**: Phase 2 (gen/go/ proto bindings from Phase 1 imported via go.mod replace directive)
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06
**Success Criteria** (what must be TRUE):
  1. `sys.containers.list()` returns all running containers by reading the Docker Unix socket (no moby/docker SDK dependency)
  2. `sys.containers.stats(id)`, `sys.containers.stop(id)`, `sys.containers.start(id)`, `sys.containers.restart(id)` work in a sysscript
  3. `sys.k3s.nodes()` and `sys.k3s.pods(namespace)` return live k3s state via Kubernetes API
  4. Every 5-second telemetry push to systemapi.io includes Docker container stats and k3s cluster state fields
  5. A sysscript containing `load("lib/helper.star", "fn")` executes without error (Thread.Load is wired)
  6. `sys.containers` and `sys.k3s` namespaces are absent (not just empty) when the agent lacks the required entitlement
**Plans**: 4 plans
Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Foundation: go.mod, entitlements, Thread.Load, client type stubs

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md — Docker client + sys.containers builtins + tests
- [x] 03-03-PLAN.md — k3s client + sys.k3s builtins + tests

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-04-PLAN.md — Telemetry extension with Docker/k3s fields + tests
**UI hint**: no

### Phase 4: Sysscript Ecosystem
**Goal**: Ops team can run health and stats checks for any service by executing a `.star` script locally with mock sys or remotely via the agent
**Depends on**: Phase 3
**Requirements**: STAR-01, STAR-02, STAR-03, STAR-04, STAR-05, STAR-06, STAR-07
**Success Criteria** (what must be TRUE):
  1. `adsops sysscript run sysscripts/services/statsagent/health.star` runs end-to-end locally via MockSys without error
  2. `sysscripts/lib/host.star`, `sysscripts/lib/docker.star`, and `sysscripts/lib/k3s.star` are importable from service scripts via `load()`
  3. Each `.star` script under `sysscripts/services/` has a corresponding passing test in `tools/adsops/tests/sysscripts/`
  4. `sysscripts/services/changes-api/stats.star` returns request counts and latency when run against a live host
**Plans**: 3 plans
Plans:
**Wave 1**
- [ ] 04-01-PLAN.md — SysscriptRunner (exec-based), CLI sub-app, runner tests

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 04-02-PLAN.md — Shared lib helpers (host.star, docker.star, k3s.star) + tests

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 04-03-PLAN.md — Service scripts (statsagent, changes-api health/stats) + tests + verification
**UI hint**: no

### Phase 5: Inventory Hierarchy
**Goal**: The hostctl inventory reflects a host->container->pod hierarchy, and infractl scan populates it automatically
**Depends on**: Phase 3
**Requirements**: INV-01, INV-02, INV-03, INV-04
**Success Criteria** (what must be TRUE):
  1. `hostctl list --children` displays containers and k3s pods nested under their parent host in tree format
  2. `infractl scan --all` discovers containers and pods on all hosts and writes them into hostctl inventory (visible in subsequent `hostctl list --children`)
  3. `hostctl export --json` produces output whose shape matches the HostRecord proto definition (no sql.NullString, uses *string pointers)
  4. Pre-condition confirmed: metadata column type verified and migrated to jsonb if needed before any scan writeback
**Plans**: 4 plans
Plans:
- [x] 03-01-PLAN.md — Foundation: go.mod, entitlements, Thread.Load, client type stubs
- [x] 03-02-PLAN.md — Docker client + sys.containers builtins + tests
- [x] 03-03-PLAN.md — k3s client + sys.k3s builtins + tests
- [ ] 03-04-PLAN.md — Telemetry extension with Docker/k3s fields + tests
**UI hint**: no

### Phase 6: Deployment Artifacts
**Goal**: Every tool has a Dockerfile and the systemapi-agent can be deployed to a k3s cluster with a single kubectl apply
**Depends on**: Phase 3 (stable agent binary to containerize; Phases 4 and 5 can be parallel)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):
  1. `docker build -f deployments/docker/Dockerfile.hostctl .` produces a working image (CGO handled correctly per sqlite driver in use)
  2. `docker build -f deployments/docker/Dockerfile.infractl .` produces a working image
  3. `kubectl apply -f deployments/kubernetes/` deploys systemapi-agent as a DaemonSet with Docker socket access and k3s kubeconfig mounted
  4. `docker compose --profile tools up` starts hostctl and statsagent services alongside existing services
  5. RBAC manifest creates ServiceAccount, ClusterRole, and ClusterRoleBinding for the agent DaemonSet
**Plans**: 4 plans
Plans:
- [x] 03-01-PLAN.md — Foundation: go.mod, entitlements, Thread.Load, client type stubs
- [x] 03-02-PLAN.md — Docker client + sys.containers builtins + tests
- [x] 03-03-PLAN.md — k3s client + sys.k3s builtins + tests
- [ ] 03-04-PLAN.md — Telemetry extension with Docker/k3s fields + tests
**UI hint**: no

## Progress

**Execution Order:**
Phases 1 -> 2 -> 3 are strictly sequential (proto dependency chain).
Phases 4, 5, 6 unlock after Phase 3; Phases 5 and 6 can run in parallel.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Proto Data Contracts | 0/3 | Planning complete | - |
| 2. Python3 Package | 0/3 | Planning complete | - |
| 3. systemapi-agent Improvements | 0/? | Not started | - |
| 4. Sysscript Ecosystem | 0/3 | Planning complete | - |
| 5. Inventory Hierarchy | 0/? | Not started | - |
| 6. Deployment Artifacts | 0/? | Not started | - |
