# Phase 3: systemapi-agent Improvements - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 3-systemapi-agent-improvements
**Areas discussed:** Docker socket path, k3s credential discovery, Thread.Load script model, Entitlement design

---

## Docker Socket Path

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded /var/run/docker.sock | Universal default on all target platforms | |
| DOCKER_HOST env var | Read DOCKER_HOST if set, fall back to /var/run/docker.sock — matches Docker CLI convention | ✓ |
| Agent flag --docker-socket | CLI flag, most explicit but adds complexity to startup | |

**User's choice:** DOCKER_HOST env var
**Notes:** Consistent with Docker CLI behavior; matches the kind of convention ops engineers already know.

### Docker error handling

| Option | Description | Selected |
|--------|-------------|----------|
| Return empty list + log error | Non-fatal; script continues with empty list | ✓ |
| Return Starlark error | Script can catch and handle | |
| You decide | Match existing patterns | |

**User's choice:** Return empty list + log error

---

## k3s Credential Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Standard k3s path first | Try /etc/rancher/k3s/k3s.yaml first, then KUBECONFIG env var | ✓ |
| KUBECONFIG env var only | Explicit but requires manual setup | |
| Agent flag --kubeconfig | Most explicit, requires updating service definition per host | |

**User's choice:** Standard k3s path first (with KUBECONFIG fallback)

### k3s error handling

| Option | Description | Selected |
|--------|-------------|----------|
| Return empty list + log error | Mirrors container behavior; non-fatal | ✓ |
| Return Starlark error | Script handles exception | |
| You decide | Match containers | |

**User's choice:** Return empty list + log error

### k3s.apply() scope

| Option | Description | Selected |
|--------|-------------|----------|
| All three (nodes, pods, apply) | Per AGENT-04 requirements | ✓ |
| Read-only first (nodes + pods only) | Defer apply as riskiest op | |
| You decide | Follow requirements as written | |

**User's choice:** All three — include apply(yaml_str) in Phase 3

---

## Thread.Load Script Model

| Option | Description | Selected |
|--------|-------------|----------|
| Agent-local script directory | Agent reads from /etc/systemapi/scripts/; scripts deployed there separately | ✓ |
| Script bundle in message | CommandMessage carries a scripts map; in-memory resolution | |
| You decide | Pick simpler implementation | |

**User's choice:** Agent-local script directory

### Script base directory

| Option | Description | Selected |
|--------|-------------|----------|
| /etc/systemapi/scripts/ hardcoded | Consistent install path, no flag needed | ✓ |
| --sysscript-dir flag | Configurable at startup | |
| SYSTEMAPI_SCRIPT_DIR env var | Consistent with DOCKER_HOST approach | |

**User's choice:** /etc/systemapi/scripts/ hardcoded

### Missing script behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Starlark load error | Thread.Load returns error; script fails fast | ✓ |
| Return empty module | Silent failure; confusing downstream errors | |
| You decide | Standard Starlark behavior | |

**User's choice:** Starlark load error (fail fast)

---

## Entitlement Design

| Option | Description | Selected |
|--------|-------------|----------|
| New bool fields AllowContainers + AllowK3s | Consistent with AllowExec pattern | ✓ |
| Capabilities []string list | More extensible but changes existing struct shape | |
| You decide | Follow AllowExec pattern | |

**User's choice:** New bool fields

### Enforcement location

| Option | Description | Selected |
|--------|-------------|----------|
| buildSysModule conditionally includes namespaces | Keys absent from sysDict when not granted; satisfies "absent not empty" criterion | ✓ |
| Each method checks entitlement | Namespace present but methods return errors | |

**User's choice:** buildSysModule conditional inclusion

---

## Claude's Discretion

- Docker API version to target
- k8s API client implementation details (raw HTTP vs client-go)
- JSON struct tags and exact field naming for telemetry additions
- Error logging verbosity
- Whether to cache Docker/k3s data between telemetry ticks

## Deferred Ideas

None — discussion stayed within phase scope.
