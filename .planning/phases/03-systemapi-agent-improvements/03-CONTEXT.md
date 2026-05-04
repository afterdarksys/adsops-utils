# Phase 3: systemapi-agent Improvements - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the `systemapi-agent` Go repo (`/Users/ryan/development/systemapi.io/systemapi-agent`) with:
- Real `sys.containers` module: `list()`, `stats(id)`, `stop/start/restart(id)` via Docker Unix socket (no moby/docker SDK)
- New `sys.k3s` module: `nodes()`, `pods(namespace)`, `apply(yaml_str)` via Kubernetes API
- `Thread.Load` wired so sysscripts can call `load("lib/helper.star", "fn")` from `/etc/systemapi/scripts/`
- Extended `TelemetryPayload` with docker container stats and k3s cluster state (every 5s push)
- Entitlement enforcement: `sys.containers` and `sys.k3s` absent from Starlark env when not granted

All work committed to the separate `systemapi-agent` repo, not `adsops-utils`.

Does NOT deliver: sysscript library files (.star), per-service scripts, inventory hierarchy (Phases 4–5).

</domain>

<decisions>
## Implementation Decisions

### Docker Socket
- **D-01:** Read `DOCKER_HOST` env var if set; fall back to `/var/run/docker.sock`. Matches Docker CLI convention.
- **D-02:** On socket unavailable or request failure, `sys.containers.list()` (and all container methods) return an empty list and log the error. Non-fatal — script continues.
- **D-03:** Use raw HTTP over Unix socket (custom `http.Transport` with `net.Dial("unix", socketPath)`) — no moby/docker SDK dependency per success criteria #1.

### k3s Credential Discovery
- **D-04:** Try `/etc/rancher/k3s/k3s.yaml` first, then fall back to `KUBECONFIG` env var. Standard k3s install path requires no additional configuration.
- **D-05:** On k3s unavailable (no kubeconfig, API unreachable), `sys.k3s.nodes()` and `sys.k3s.pods()` return empty list and log the error. Non-fatal — mirrors container behavior.
- **D-06:** `sys.k3s.apply(yaml_str)` is in scope for Phase 3 (per AGENT-04). Implement as raw HTTP PATCH/POST to the Kubernetes API.

### Thread.Load — Script Loading Model
- **D-07:** `load("lib/helper.star", "fn")` resolves relative to `/etc/systemapi/scripts/` (hardcoded base directory). Scripts are deployed to that directory on the host via external means (scp, config management, etc.).
- **D-08:** Thread.Load is set on the `starlark.Thread` in `SysscriptEngine.Execute()` to read from `/etc/systemapi/scripts/<path>`.
- **D-09:** If a load() target doesn't exist in `/etc/systemapi/scripts/`, `Thread.Load` returns an error — Starlark propagates a load error. Script fails fast (no silent empty module).

### Entitlement Design
- **D-10:** Add `AllowContainers bool` and `AllowK3s bool` fields to the `Entitlements` struct. Consistent with existing `AllowExec bool` pattern.
- **D-11:** Enforcement is in `buildSysModule()`: if `!AllowContainers`, the `"containers"` key is not added to `sysDict` at all. Same for `"k3s"` and `AllowK3s`. The namespace is absent from the Starlark env, not just empty. This satisfies success criteria #6.

### Telemetry (carry-forward from ROADMAP)
- **D-12:** Proto bindings from `adsops-utils/gen/go/adsops/v1/` imported via `go.mod replace` directive (per ROADMAP Phase 3 dependency note). `TelemetryPayload` extended with `Docker []ContainerStats` and `K3s K3sStats` fields aligned to proto definitions.

### Claude's Discretion
- Docker API version to target (use `v1.41` or negotiate via API version negotiation endpoint)
- k8s API client implementation details (raw HTTP with TLS from kubeconfig, no k8s client-go dependency unless needed)
- JSON struct tags and exact field naming for telemetry additions
- Error logging verbosity and format (use existing `log.Printf` pattern)
- Whether to cache Docker/k3s data between telemetry ticks or re-query every 5s

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### systemapi-agent source (target repo)
- `/Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go` — SysscriptEngine, Execute(), buildSysModule(), Entitlements struct
- `/Users/ryan/development/systemapi.io/systemapi-agent/sys_advanced.go` — existing stub implementations (containersRun, alertsPush, etc.)
- `/Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go` — TelemetryPayload struct and gatherTelemetry() — add docker/k3s fields here
- `/Users/ryan/development/systemapi.io/systemapi-agent/main.go` — CommandMessage, WebSocket message loop, how entitlements arrive

### Proto bindings (Phase 1 output — imported via go.mod replace)
- `gen/go/adsops/v1/` — generated Go proto bindings for ContainerStats, K3sStats, TelemetryPayload
- `proto/` — source .proto definitions if struct shape needs to be verified

### Requirements
- `.planning/REQUIREMENTS.md` §systemapi-agent Improvements — AGENT-01 through AGENT-06
- `.planning/ROADMAP.md` §Phase 3 — success criteria (6 items) and dependency note

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SysscriptEngine` / `buildSysModule()` in `sysscript.go` — add `sys.k3s` struct the same way `sys.containers` is already wired
- `Entitlements` struct in `sysscript.go` — add `AllowContainers` and `AllowK3s` bool fields following the `AllowExec` pattern
- `execRun` entitlement check pattern (`if !engine.Entitlements.AllowExec { return error }`) — do NOT use for containers/k3s; use the buildSysModule conditional-include approach instead (D-11)

### Established Patterns
- All sys.* builtins follow `func (engine *SysscriptEngine) methodName(thread, b, args, kwargs)` signature
- `starlark.UnpackArgs` used for argument parsing in every existing builtin
- Error returns use `starlark.None, fmt.Errorf(...)` pattern
- `log.Printf` for all agent-side logging (no structured logger)
- `starlarkstruct.FromStringDict(starlark.String("name"), dict)` to assemble nested modules

### Integration Points
- `buildSysModule()` in `sysscript.go` — add `sys.k3s` to `sysDict` here (conditionally on `AllowK3s`)
- `Execute()` in `sysscript.go` — set `thread.Load` here before `starlark.ExecFile`
- `gatherTelemetry()` in `telemetry.go` — add Docker and k3s data collection calls here
- `go.mod` — add `replace` directive pointing to `adsops-utils/gen/go/` for proto import

</code_context>

<specifics>
## Specific Ideas

- `DOCKER_HOST` env var approach matches Docker CLI convention — if someone has a non-standard socket, they already know to set this var.
- `/etc/systemapi/scripts/` as the sysscript base dir keeps it consistent with `/etc/systemapi/` as a natural agent config/data root.
- The `load()` path is relative to the base dir, so `load("lib/helper.star", "fn")` reads `/etc/systemapi/scripts/lib/helper.star` — this aligns exactly with how Phase 4 sysscript library files will be named and organized.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-systemapi-agent-improvements*
*Context gathered: 2026-05-04*
