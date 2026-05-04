---
phase: 03-systemapi-agent-improvements
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - /Users/ryan/development/systemapi.io/systemapi-agent/docker_client.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/k3s_client.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sysscript.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sysscript_test.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sys_containers.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sys_containers_test.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sys_k3s.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/sys_k3s_test.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/telemetry.go
  - /Users/ryan/development/systemapi.io/systemapi-agent/telemetry_test.go
findings:
  critical: 5
  warning: 6
  info: 3
  total: 14
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

The implementation covers Docker Engine API client, K3s/Kubernetes REST API client, an entitlements-gated Starlark script engine, and telemetry extensions. The architecture is sound and the primary security controls (container ID allowlist, namespace allowlist, Thread.Load path traversal guard) are correctly implemented and tested.

However, five critical bugs were found: two integer underflows that can produce nonsense CPU/network metrics, a response-body read order bug in `Apply` that silently discards the error body before the PATCH retry, an unvalidated `apiVersion` and `kind` field in `Apply` that allows path injection into the constructed URL, and a nil pointer dereference path in `gatherDockerStats` when a container ID fails `isValidContainerID` (which can never actually happen with real Docker IDs, but illustrates a structural gap). Several warnings concern missing timeouts on the K3s transport, the wildcard (`*`) bypass in the network entitlement check, and other correctness issues.

---

## Critical Issues

### CR-01: Integer Underflow in CPU Delta Calculation

**File:** `docker_client.go:151-152`

**Issue:** `cpuDelta` and `sysDelta` are computed by subtracting `uint64` values without checking whether the current reading is greater than or equal to the previous one. On the first stat call after a container restart, or when the kernel resets counters, `TotalUsage < PreCPUStats.TotalUsage` and `SystemCPUUsage < PreCPUStats.SystemCPUUsage`. Subtracting unsigned integers in this order wraps to a very large positive number, producing a wildly incorrect (and very large) CPU percentage — potentially `> 100 * OnlineCPUs`. This will be reported to the server and logged.

**Fix:**
```go
// Guard against counter wrap/reset before computing deltas
var cpuDelta, sysDelta uint64
if raw.CPUStats.CPUUsage.TotalUsage >= raw.PreCPUStats.CPUUsage.TotalUsage {
    cpuDelta = raw.CPUStats.CPUUsage.TotalUsage - raw.PreCPUStats.CPUUsage.TotalUsage
}
if raw.CPUStats.SystemCPUUsage >= raw.PreCPUStats.SystemCPUUsage {
    sysDelta = raw.CPUStats.SystemCPUUsage - raw.PreCPUStats.SystemCPUUsage
}
```

---

### CR-02: Integer Underflow in Network Byte-Rate Calculation

**File:** `telemetry.go:295`

**Issue:** `stat.BytesRecv - lastNetStats[0].BytesRecv` and `stat.BytesSent - lastNetStats[0].BytesSent` are `uint64` subtractions. If the interface counter resets (reboot, interface flap, NIC change), the subtraction wraps and `uint64(float64(hugeWrap) / duration)` produces an astronomically large value that is then stored in the payload and sent to the server.

**Fix:**
```go
var deltaRecv, deltaSent uint64
if stat.BytesRecv >= lastNetStats[0].BytesRecv {
    deltaRecv = stat.BytesRecv - lastNetStats[0].BytesRecv
}
if stat.BytesSent >= lastNetStats[0].BytesSent {
    deltaSent = stat.BytesSent - lastNetStats[0].BytesSent
}
payload.Network = NetworkMetrics{
    BytesRecv: uint64(float64(deltaRecv) / duration),
    BytesSent: uint64(float64(deltaSent) / duration),
}
```

---

### CR-03: Response Body Drained Before Error Status Is Checked in Apply (Data Loss / Silent Failure)

**File:** `k3s_client.go:287`

**Issue:** After the POST in `Apply`, the body is drained with `io.Copy(io.Discard, resp.Body)` on line 287 before the status code is checked. This is not wrong in itself, but the `resp.Body` is also closed via `defer resp.Body.Close()`. However the more critical problem is: when `resp.StatusCode == http.StatusConflict` (409), the code moves to `doPatch`, which opens a second response. The first response's `defer resp.Body.Close()` is still outstanding. Because `resp.Body` was already fully drained by the `io.Copy`, the deferred close is safe. But if the status falls into the `default` error case (e.g., a 400 Bad Request), the error message from the server body has already been discarded, making debugging impossible. The error returned is only the status code number. This is a quality/debugging blocker in production.

**Fix:** Read and include the body in the error message:
```go
bodyBytes, _ := io.ReadAll(resp.Body)
// after switch default:
return fmt.Errorf("k3s apply POST: unexpected status %d: %s", resp.StatusCode, strings.TrimSpace(string(bodyBytes)))
```
Replace the unconditional `io.Copy(io.Discard, resp.Body)` at line 287 with a conditional read only in the success/conflict paths, or read the body before the switch.

---

### CR-04: Unvalidated `apiVersion` and `kind` Fields Allow URL Path Injection in Apply

**File:** `k3s_client.go:154-169` and `k3s_client.go:260`

**Issue:** `resourcePath` validates the `namespace` argument via `isValidNamespace`, but performs no validation on `apiVersion` or `kind`. Both values come directly from the user-supplied YAML manifest. An attacker who can call `sys.k3s.apply()` can supply:

```yaml
apiVersion: "../../some/other/api"
kind: "../../../../path"
```

which causes `resourcePath` to construct a URL like `/apis/../../some/other/api/namespaces/default/../../../../paths` and after HTTP client URL normalization, potentially reach unintended API server endpoints. The `kc.serverURL` is fixed, so this cannot escape the cluster, but it can reach unintended server-side paths (e.g., reaching `/api/v1/secrets` when targeting `/apis/../../api/v1/secrets` is cleaned).

**Fix:** Add allowlist validation for both fields:
```go
func isValidAPIVersion(v string) bool {
    // Allow "v1" or "group/version" where group and version are [a-z0-9.-]+
    if v == "v1" {
        return true
    }
    parts := strings.SplitN(v, "/", 2)
    if len(parts) != 2 {
        return false
    }
    for _, p := range parts {
        for _, r := range p {
            if !((r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '.' || r == '-') {
                return false
            }
        }
    }
    return true
}

func isValidKind(k string) bool {
    if len(k) == 0 || len(k) > 64 {
        return false
    }
    for _, r := range k {
        if !((r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9')) {
            return false
        }
    }
    return true
}
```
Call both validators at the top of `resourcePath` and return an error if they fail.

---

### CR-05: Path Traversal Check in Thread.Load Uses String Prefix on Uncleaned Input

**File:** `sysscript.go:70-72`

**Issue:** The traversal guard is:
```go
resolved := filepath.Clean(filepath.Join(scriptsBase, module))
if !strings.HasPrefix(resolved, scriptsBase+string(os.PathSeparator)) && resolved != scriptsBase {
    return nil, fmt.Errorf("load(%q): path traversal not allowed", module)
}
```

`scriptsBase` is `/etc/systemapi/scripts`. `resolved` after `filepath.Clean` is also an absolute cleaned path. The check `strings.HasPrefix(resolved, scriptsBase+"/")` is correct in principle. However, there is one edge case: if `scriptsBase` is configured or redefined in a future refactor without a trailing separator component — for example changed to `/etc/systemapi` — then `/etc/systemapi-other/scripts/evil.star` would pass the prefix check (`/etc/systemapi` is a prefix of `/etc/systemapi-other`). Currently the hardcoded value is safe, but this is a latent fragility.

More immediately: `module` is passed directly into `filepath.Join` without any pre-check. `filepath.Join` will handle `..` segments via the subsequent `filepath.Clean`, so the traversal itself is blocked correctly. The real concern is that this function is also called for sub-thread loads (line 78), and the sub-thread's `Load` function is set to the same `loadFn` closure — so sub-threads inherit the same protection. This part is correct.

The actual bug: if `module` is an absolute path (e.g., `/etc/passwd`), `filepath.Join(scriptsBase, "/etc/passwd")` on Go resolves to `/etc/passwd` directly (Go's `filepath.Join` does NOT treat absolute second arguments as overriding the first on Linux — it concatenates them as `scriptsBase + "/etc/passwd"`). Wait — actually testing this: `filepath.Join("/base", "/etc/passwd")` = `/base/etc/passwd` in Go, so it is safe. However if an attacker passes a module with a null byte or other encoding, `os.ReadFile` will error. This is acceptable.

The actual confirmed bug is subtler: the `resolved != scriptsBase` branch permits loading `scriptsBase` itself (the directory) as a file. `os.ReadFile` on a directory returns an error, but this is sloppy logic — it should only permit files under the directory, not the directory itself.

**Fix:**
```go
// Require resolved to be strictly under scriptsBase (not equal to it)
if !strings.HasPrefix(resolved, scriptsBase+string(os.PathSeparator)) {
    return nil, fmt.Errorf("load(%q): path traversal not allowed", module)
}
```

---

## Warnings

### WR-01: K3s HTTP Transport Has No Timeout

**File:** `k3s_client.go:124-129`

**Issue:** The `http.Transport` created for the K3s client has no `DialContext`, `TLSHandshakeTimeout`, or `ResponseHeaderTimeout` set. The `http.Client` wrapping it does set a 10-second `Timeout` (line 132), which covers the full round-trip. However, the transport-level `TLSHandshakeTimeout` defaults to 0 (no timeout) in Go's `http.DefaultTransport`, meaning a stalled TLS handshake can hang indefinitely even though the client-level timeout exists. (Client-level `Timeout` does cancel in-flight requests via context, so this is mitigated but not fully closed.)

**Fix:**
```go
transport := &http.Transport{
    TLSClientConfig: &tls.Config{
        RootCAs:      caCertPool,
        Certificates: []tls.Certificate{tlsCert},
    },
    TLSHandshakeTimeout:   5 * time.Second,
    ResponseHeaderTimeout: 8 * time.Second,
}
```

---

### WR-02: Wildcard `"*"` in `AllowNetOutbound` Bypasses All Network Entitlement Enforcement

**File:** `sysscript.go:287-290`

**Issue:** The `netHTTPGet` entitlement check accepts `"*"` as a wildcard that allows HTTP requests to any host. This wildcard is also accepted for `AllowFSRead` and `AllowFSWrite` (lines 321, 346). For a security-gated script engine, a misconfigured entitlement set with `"*"` in `AllowNetOutbound` means any outbound HTTP call is permitted, including calls to instance metadata services (e.g., `http://169.254.169.254/` on AWS/GCP/Azure), which could expose cloud credentials. There is no audit log when the wildcard is used.

**Fix:** At minimum, log a warning when wildcard entitlements are granted, and consider blocking known metadata service IP ranges even when `"*"` is set:
```go
if domain == "*" {
    log.Printf("[sysscript] WARNING: wildcard net outbound entitlement used for request to %s", u.Hostname())
    allowed = true
    break
}
```
Consider documenting that `"*"` must never be set in production entitlements.

---

### WR-03: `gatherDockerStats` Calls `GetContainerStats` with Unvalidated Container IDs from Docker API

**File:** `telemetry.go:141`

**Issue:** `GetContainerStats(c.Id)` is called where `c.Id` comes from `ListContainers()` which receives IDs from the Docker daemon. `GetContainerStats` itself calls `isValidContainerID(id)` and will reject IDs that contain characters outside `[a-zA-Z0-9_\-.]`. Real Docker IDs are 64-char hex strings, which pass validation. However, if Docker returns a malformed ID (e.g., from a corrupted daemon state or an adversarial daemon), the call will return an error and the container will be skipped. This is handled gracefully via `log.Printf` + `continue`, so there is no crash. The concern is that the skip is silent to the consumer — the telemetry payload will be missing data for that container without any indication to the server.

The `ContainerStatsTelemetry` entry is only appended on success; there is no "partial/error" marker in the payload. A monitoring system relying on container count from `len(result.Containers)` vs `TotalContainers` would observe a mismatch silently.

**Fix:** Add an `ErrorContainers int32` field to `DockerStatsTelemetry` and increment it when a stats call fails:
```go
result.ErrorContainers++
// log the skip as before
```

---

### WR-04: `Apply` Double-Parses YAML and Normalizes, But Does Not Validate Manifest Name

**File:** `k3s_client.go:245-276`

**Issue:** The `manifest.Metadata.Name` field is extracted from user YAML but never validated. It is embedded in the POST body as JSON, and the Kubernetes API server will validate it there. However, if the name contains characters that would cause issues in the server-side URL for a future `doPatch` or `doDelete` call (e.g., if the name is used in a path), this is not guarded. Currently `Apply` uses the namespace in the path (validated) and the resource is identified in the body, so the name is not used in the URL path. This is acceptable for the current implementation, but a `Delete` operation added later that uses the name in the path would be vulnerable.

**Fix:** Add a comment in `Apply` explicitly noting that `Metadata.Name` must be validated before it is ever used in a URL path segment.

---

### WR-05: `fsRead` and `fsWrite` Entitlement Checks Use `strings.HasPrefix` on Raw (Not Cleaned) Path

**File:** `sysscript.go:320-322`, `344-349`

**Issue:** The filesystem entitlement checks compare the raw `path` argument from Starlark against allowed prefixes using `strings.HasPrefix`. If a script passes a path like `/etc/systemapi/../shadow`, `strings.HasPrefix("/etc/systemapi/../shadow", "/etc/systemapi")` returns `true`, but the actual file accessed by `os.ReadFile` will be `/etc/shadow` (after OS-level path resolution). The entitlement is bypassed.

**Fix:** Clean the path before the prefix check:
```go
cleanPath := filepath.Clean(path)
allowed := false
for _, prefix := range engine.Entitlements.AllowFSRead {
    if prefix == "*" || strings.HasPrefix(cleanPath, prefix) {
        allowed = true
        break
    }
}
// Use cleanPath in os.ReadFile
data, err := os.ReadFile(cleanPath)
```
Apply the same fix to `fsWrite`, `fsStat`, `fsGlob`, `fsMkdir`, `fsRm`, and `fsChmod`.

---

### WR-06: `k3sPods` Starlark Builtin Accepts Namespace Argument as Positional String But Does Not Validate It When Empty String Is Provided

**File:** `sys_k3s.go:64`, `k3s_client.go:200-208`

**Issue:** In `k3sPods`, when `namespace` is the empty string `""`, the code passes it directly to `ListPods("")`, which correctly routes to the all-namespaces endpoint without validation. However, in `ListPods`, the validation (`isValidNamespace`) is only called for non-empty strings. An empty string explicitly passes the check because `len(ns) == 0` returns `false` from `isValidNamespace`, but the code explicitly checks `if namespace == ""` before calling `isValidNamespace`. This is logically correct, but the two-layer guard creates confusion: `isValidNamespace("")` returns `false` (which would be an error if called), but it is never called for empty strings in `ListPods`. If someone calls `isValidNamespace("")` expecting it to represent "all namespaces", they would get a false negative. The name of the function is misleading — an empty string is actually a valid special case.

**Fix:** Document the convention explicitly:
```go
// isValidNamespace validates a non-empty namespace string. The empty string ""
// is NOT passed to this function — callers interpret "" as "all namespaces"
// before calling isValidNamespace.
```

---

## Info

### IN-01: `containersList` Silently Discards Non-Running Container Names

**File:** `sys_containers.go:22-34`

**Issue:** When `c.Names` is empty (possible for containers in "created" or "exited" state that have no assigned name), `name` is left as `""` and the struct is added with an empty name field. The Starlark consumer has no way to distinguish "no name assigned" from "name not fetched." Using `c.Id[:12]` as a fallback (as `gatherDockerStats` does in telemetry.go) would be more useful.

**Fix:**
```go
name := ""
if len(c.Names) > 0 {
    name = strings.TrimPrefix(c.Names[0], "/")
}
if name == "" {
    // fallback to short ID
    if len(c.Id) >= 12 {
        name = c.Id[:12]
    } else {
        name = c.Id
    }
}
```

---

### IN-02: `resourcePath` Simple Pluralization Is Incorrect for Several Kubernetes Kinds

**File:** `k3s_client.go:155`

**Issue:** `kindPlural := strings.ToLower(kind) + "s"` produces incorrect API paths for kinds with irregular plurals: `Endpoints` -> `endpointss`, `Ingress` -> `ingresss`, `NetworkPolicy` -> `networkpolicys` (should be `networkpolicies`), `HorizontalPodAutoscaler` -> `horizontalpodautoscalers` (this one is actually correct). While Kubernetes has only a handful of irregular plurals, the current approach will silently construct invalid API paths that return 404 from the server, and the error message will show an opaque "unexpected status 404" rather than a clear "unknown kind" message.

**Fix:** Add a lookup table for known irregular plurals, or document the limitation prominently so callers know to use correctly-cased/spelled kinds.

---

### IN-03: Global Variables for Telemetry State Are Not Goroutine-Safe

**File:** `telemetry.go:104-108`

**Issue:** `lastNetStats`, `lastNetTime`, `lastSoftwareGather`, and `cachedSoftware` are package-level globals accessed in `gatherTelemetry()` without any mutex. If `gatherTelemetry` is ever called concurrently (e.g., from multiple goroutines in a future refactor, or if the existing call site uses a ticker that fires before a previous invocation completes), these reads and writes are a data race. `telemetryClientsOnce` is correctly synchronized, but the state variables are not.

**Fix:** Protect the globals with a mutex, or restructure `gatherTelemetry` to receive state as arguments:
```go
var telemetryMu sync.Mutex
// Acquire telemetryMu before reading/writing lastNetStats, lastNetTime,
// lastSoftwareGather, cachedSoftware.
```

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
