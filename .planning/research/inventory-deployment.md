# Research: Inventory Hierarchy + Deployment Artifacts

**Researched:** 2026-05-03
**Scope:** hostctl hierarchy extension, infractl scan writeback, Dockerfiles, k3s manifests

---

## Topic 1: Hierarchical Inventory Without Schema Migration

### 1. Expressing the baremetal → container → pod hierarchy via metadata JSON

The existing `metadata map[string]interface{}` column in `inventory_resources` is the correct place to store children without a schema migration. The pattern is a versioned nested structure under a `"children"` key.

**Recommended metadata shape:**

```json
{
  "ip": "10.0.1.5",
  "size": "m5.2xlarge",
  "_children_version": 1,
  "children": [
    {
      "kind": "container",
      "id": "a3f91bc2",
      "name": "nginx-proxy",
      "image": "nginx:1.25",
      "status": "running",
      "ports": ["80:80", "443:443"],
      "discovered_at": "2026-05-03T12:00:00Z"
    },
    {
      "kind": "pod",
      "id": "default/nginx-6d4cf56db-xk9vp",
      "name": "nginx-6d4cf56db-xk9vp",
      "namespace": "default",
      "node": "worker-01",
      "status": "Running",
      "images": ["nginx:1.25"],
      "labels": {"app": "nginx"},
      "discovered_at": "2026-05-03T12:00:00Z"
    }
  ]
}
```

Key decisions:
- `kind` field discriminates container vs pod vs future types (VM, process).
- `_children_version: 1` lets you evolve the schema later without inspecting content.
- Container `id` is the short Docker ID (12-char). Pod `id` is `namespace/podname` — matches kubectl output and is globally unique within a cluster.
- `discovered_at` timestamp lets infractl scan detect stale children and prune them on next scan.
- Do NOT store container/pod resource costs here — those belong on the parent host's `average_daily_cost` column.

**Postgres JSON query** (for inventory search without schema change):

```sql
-- Find hosts running a specific container image
SELECT hostname FROM inventory_resources
WHERE metadata->'children' @> '[{"image": "nginx:1.25"}]';

-- Count containers per host
SELECT hostname, jsonb_array_length(metadata->'children') AS child_count
FROM inventory_resources
WHERE metadata ? 'children';
```

The `metadata` column must be `jsonb` (not `json`) for these operators to work. Confirm with `\d inventory_resources` — if it is `json`, a single `ALTER COLUMN metadata TYPE jsonb USING metadata::jsonb` is a non-destructive migration.

### 2. Adding --children to hostctl list without breaking existing output

`ListOptions` struct in `types.go` needs one field addition:

```go
type ListOptions struct {
    Status      string
    Environment string
    Type        string
    Provider    string
    Region      string
    Limit       int
    ShowChildren bool   // NEW — set by --children flag
}
```

No database query changes are needed. Children already live in `metadata` which is fetched on every query. The flag only controls rendering in `output.go`.

**Table output (default, no --children):** unchanged — the `printResourceTable` function already ignores unknown metadata keys.

**Tree output (--children flag set):** add a `printResourceTree` function alongside the existing `printResource`/`printResourceTable`/`printResourceJSON`:

```go
func printResourceTree(resources []*Resource) {
    for _, r := range resources {
        fmt.Printf("%s%s%s (%s/%s) [%s]\n",
            colorBold, r.Hostname, colorReset, r.Type, r.Provider, r.Status)

        children, _ := extractChildren(r.Metadata)
        for i, child := range children {
            prefix := "├─"
            if i == len(children)-1 {
                prefix = "└─"
            }
            fmt.Printf("  %s %s  %s  %s\n",
                prefix, child["kind"], child["name"], child["status"])
        }
    }
}

func extractChildren(m map[string]interface{}) ([]map[string]interface{}, bool) {
    raw, ok := m["children"]
    if !ok {
        return nil, false
    }
    // type-assert through []interface{} since JSON unmarshals to that
    arr, ok := raw.([]interface{})
    if !ok {
        return nil, false
    }
    out := make([]map[string]interface{}, 0, len(arr))
    for _, item := range arr {
        if child, ok := item.(map[string]interface{}); ok {
            out = append(out, child)
        }
    }
    return out, true
}
```

JSON output (`--json`) requires no change — `json.MarshalIndent(r, "", "  ")` already includes `Metadata`, so children appear automatically in JSON output when present.

**Flag wiring in commands.go:**

```go
listCmd.Flags().BoolVar(&listOpts.ShowChildren, "children", false, "show containers and pods under each host")
```

Backwards compatibility: hosts with no `"children"` key in metadata render identically to today. The flag is purely additive.

### 3. JSON export format aligned with proto HostRecord shape

Based on the current `Resource` struct and standard proto naming conventions, the recommended JSON export format for proto alignment is:

```json
{
  "id": 42,
  "resource_name": "worker-01.dc1.example.com",
  "hostname": "worker-01.dc1.example.com",
  "type": "baremetal",
  "provider": "self-hosted",
  "region": "dc1",
  "status": "active",
  "environment": "production",
  "owners": ["ops-team"],
  "mailgroups": ["ops@example.com"],
  "metadata": {
    "ip": "10.0.1.5",
    "size": "48c/256g",
    "_children_version": 1,
    "children": [...]
  },
  "average_daily_cost": 12.50,
  "average_monthly_cost": 375.00,
  "external_id": "srv-001",
  "external_url": "https://portal.example.com/hosts/srv-001",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-05-03T12:00:00Z"
}
```

Proto alignment notes:
- Use snake_case field names everywhere — proto3 JSON mapping uses snake_case by default.
- `sql.NullString` and `sql.NullFloat64` fields currently marshal as `{"String":"...","Valid":true}` — this is wrong for proto alignment. Fix: add `MarshalJSON`/`UnmarshalJSON` methods to `Resource`, or replace `sql.Null*` fields with pointer types (`*string`, `*float64`) which marshal as `null` when absent and as the bare value when present.
- Timestamps should be RFC3339/ISO8601 (`time.RFC3339`) not the current `"2006-01-02 15:04:05"` format used in `printResourceDetailed`. The JSON marshaler uses RFC3339 by default for `time.Time`, so `printResourceJSON` is already correct; the human-readable output functions are not relevant here.
- If a `HostRecord` proto is defined later, generate it with `protojson.Marshal` which handles the `null` vs omitted distinction correctly.

### 4. infractl scan writeback pattern for children

infractl should write discovered children as a metadata patch, not a full resource overwrite. The pattern:

```go
// In tools/infractl — scan writes back to inventory via updateResource
func writeChildrenToInventory(hostname string, children []ChildRecord) error {
    existing, err := getResourceByHostname(hostname)
    if err != nil {
        return fmt.Errorf("host %s not in inventory, skipping children writeback: %w", hostname, err)
    }

    metadata := existing.Metadata
    if metadata == nil {
        metadata = map[string]interface{}{}
    }

    childList := make([]map[string]interface{}, len(children))
    for i, c := range children {
        childList[i] = map[string]interface{}{
            "kind":          c.Kind,   // "container" or "pod"
            "id":            c.ID,
            "name":          c.Name,
            "status":        c.Status,
            "image":         c.Image,
            "discovered_at": time.Now().UTC().Format(time.RFC3339),
        }
    }

    metadata["children"] = childList
    metadata["_children_version"] = 1
    metadata["_last_scan"] = time.Now().UTC().Format(time.RFC3339)

    // Only update metadata column — leave all other fields untouched
    return patchMetadata(hostname, metadata)
}
```

`patchMetadata` should issue:
```sql
UPDATE inventory_resources
SET metadata = $1, updated_at = $2
WHERE hostname = $3
```

This is safer than routing through `updateResource` (which rebuilds metadata from opts fields) — do a direct SQL patch.

**Stale children cleanup:** on each scan, replace the entire `children` array rather than merging. This naturally removes containers/pods that no longer exist. Any child not seen in the current scan disappears from inventory on next write.

**Discovery sources infractl should query:**
- Docker: `docker ps --format json` (or Docker SDK `ContainerList`)
- k3s pods: `kubectl get pods -A -o json` (or k8s client-go against `/etc/rancher/k3s/k3s.yaml`)
- Both require the scan to run on the target host (via SSH exec) or as a privileged DaemonSet

---

## Topic 2: Dockerfile and k3s Manifest Patterns

### 1. Multi-stage Dockerfile for Go CLI tools

The statsagent Dockerfile (`tools/statsagent/deploy/Dockerfile`) is already the correct pattern for CGO_DISABLED tools. The two cases that differ from it:

**hostctl — needs SQLite (CGO required):**

```dockerfile
FROM golang:1.23-alpine AS builder

# CGO requires a C compiler
RUN apk add --no-cache gcc musl-dev sqlite-dev ca-certificates

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
# CGO_ENABLED=1 is required for mattn/go-sqlite3
RUN CGO_ENABLED=1 GOOS=linux go build \
    -ldflags="-s -w -linkmode external -extldflags '-static'" \
    -o hostctl .

# Runtime: use alpine (not distroless) because sqlite3 needs libc
FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /build/hostctl /usr/local/bin/hostctl
ENTRYPOINT ["/usr/local/bin/hostctl"]
```

Note: `-linkmode external -extldflags '-static'` produces a fully static binary on Alpine/musl. Test with `file hostctl` — should read `statically linked`. If hostctl is migrated to use the pure-Go `modernc.org/sqlite` driver, CGO_ENABLED=0 becomes possible again and the statsagent pattern applies unchanged.

**infractl — needs SSH (no CGO, but needs known_hosts handling):**

```dockerfile
FROM golang:1.23-alpine AS builder
RUN apk add --no-cache ca-certificates git

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o infractl .

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata openssh-client
# openssh-client provides ssh-keyscan and known_hosts support
# If infractl shells out to ssh binary; omit if using golang.org/x/crypto/ssh directly

COPY --from=builder /build/infractl /usr/local/bin/infractl
# SSH keys mounted at runtime via volume or secret
ENTRYPOINT ["/usr/local/bin/infractl"]
```

If infractl uses `golang.org/x/crypto/ssh` (pure Go), skip `openssh-client` and use `gcr.io/distroless/static-debian12` as the runtime image instead of alpine — it is smaller and has no shell attack surface.

### 2. k3s DaemonSet for a privileged agent (systemapi-agent pattern)

An agent needing `hostPID`, `hostNetwork`, Docker socket, and k3s kubeconfig:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: systemapi-agent
  namespace: adsops
spec:
  selector:
    matchLabels:
      app: systemapi-agent
  template:
    metadata:
      labels:
        app: systemapi-agent
    spec:
      hostPID: true
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet   # required when hostNetwork: true
      tolerations:
      - operator: Exists                   # run on all nodes including control-plane
      containers:
      - name: systemapi-agent
        image: us-ashburn-1.ocir.io/idd2oizp8xvc/systemapi-agent:latest
        imagePullPolicy: Always
        securityContext:
          privileged: true                 # required for hostPID + raw socket access
        ports:
        - containerPort: 9200
          hostPort: 9200
          name: api
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        volumeMounts:
        - name: docker-sock
          mountPath: /var/run/docker.sock
        - name: k3s-kubeconfig
          mountPath: /etc/rancher/k3s
          readOnly: true
        - name: host-proc
          mountPath: /host/proc
          readOnly: true
        resources:
          requests:
            memory: "32Mi"
            cpu: "25m"
          limits:
            memory: "128Mi"
            cpu: "200m"
      volumes:
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
          type: Socket
      - name: k3s-kubeconfig
        hostPath:
          path: /etc/rancher/k3s
          type: Directory
      - name: host-proc
        hostPath:
          path: /proc
      imagePullSecrets:
      - name: oci-registry
```

Key decisions:
- `hostNetwork: true` + `dnsPolicy: ClusterFirstWithHostNet` — the agent binds on the host network so `hostPort` is unnecessary but kept for clarity. Remove `hostPort` if you use a Service with `type: NodePort` or `externalTrafficPolicy: Local` instead.
- `privileged: true` — required for hostPID + Docker socket write access. If only read access to Docker is needed, drop `privileged: true` and use a group/supplementalGroups approach instead.
- `tolerations: [{operator: Exists}]` — runs on control-plane nodes too; narrow this if you only want worker nodes.
- `NODE_NAME` env var injected via Downward API — lets the agent self-register in inventory by node name.

### 3. statsagent DaemonSet and how it differs from systemapi-agent

The statsagent DaemonSet should be less privileged than systemapi-agent because statsagent is read-only (metrics collection) vs systemapi-agent which needs write access for management operations.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: statsagent
  namespace: adsops
spec:
  selector:
    matchLabels:
      app: statsagent
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  template:
    metadata:
      labels:
        app: statsagent
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9100"
        prometheus.io/path: "/metrics"
    spec:
      hostPID: true       # needed to read /proc/<pid>/* for per-process stats
      hostNetwork: false  # statsagent does NOT need host network; it just exposes a port
      tolerations:
      - operator: Exists
      containers:
      - name: statsagent
        image: us-ashburn-1.ocir.io/idd2oizp8xvc/statsagent:latest
        ports:
        - containerPort: 9100
          name: metrics
        env:
        - name: STATSAGENT_PORT
          value: "9100"
        - name: STATSAGENT_INTERVAL
          value: "15s"
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        securityContext:
          readOnlyRootFilesystem: true    # statsagent writes nothing
          runAsNonRoot: false             # /proc reads may need root depending on kernel config
        volumeMounts:
        - name: docker-sock
          mountPath: /var/run/docker.sock
          readOnly: true                  # read-only for container listing
        - name: host-proc
          mountPath: /host/proc
          readOnly: true
        - name: host-sys
          mountPath: /host/sys
          readOnly: true
        resources:
          requests:
            memory: "16Mi"
            cpu: "10m"
          limits:
            memory: "64Mi"
            cpu: "100m"
        livenessProbe:
          httpGet:
            path: /health
            port: 9100
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 9100
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
          type: Socket
      - name: host-proc
        hostPath:
          path: /proc
      - name: host-sys
        hostPath:
          path: /sys
      imagePullSecrets:
      - name: oci-registry
```

**Difference table: statsagent vs systemapi-agent DaemonSet**

| Concern | statsagent | systemapi-agent |
|---|---|---|
| `hostNetwork` | false — binds on pod network | true — binds on host network |
| `privileged` | false — read-only mounts | true — needs write/exec on host |
| Docker socket | read-only mount | read-write mount |
| k3s kubeconfig | not needed | mounted from host |
| `readOnlyRootFilesystem` | true | false (may write temp files) |
| Prometheus annotations | yes — scraped by Prometheus | no — not a metrics exporter |
| Resource requests | 10m CPU / 16Mi RAM | 25m CPU / 32Mi RAM |
| Purpose | passive metrics collection | active host management / scan |

### 4. docker-compose for local dev stack with hostctl and statsagent

Extend the existing `deployments/docker/docker-compose.yml` (which has postgres, redis, api, worker):

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: adsops-postgres
    environment:
      POSTGRES_USER: adsops
      POSTGRES_PASSWORD: adsops_dev_password
      POSTGRES_DB: adsops_changes
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../../migrations:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U adsops -d adsops_changes"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: adsops-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ../..
      dockerfile: deployments/docker/Dockerfile.api
    container_name: adsops-api
    environment:
      ADSOPS_ENVIRONMENT: development
      ADSOPS_PORT: 8080
      ADSOPS_DATABASE_HOST: postgres
      ADSOPS_DATABASE_PORT: 5432
      ADSOPS_DATABASE_USER: adsops
      ADSOPS_DATABASE_PASSWORD: adsops_dev_password
      ADSOPS_DATABASE_DBNAME: adsops_changes
      ADSOPS_DATABASE_SSLMODE: disable
      ADSOPS_REDIS_HOST: redis
      ADSOPS_REDIS_PORT: 6379
      ADSOPS_JWT_SECRET_KEY: dev_secret
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build:
      context: ../..
      dockerfile: deployments/docker/Dockerfile.worker
    container_name: adsops-worker
    environment:
      ADSOPS_DATABASE_HOST: postgres
      ADSOPS_DATABASE_PORT: 5432
      ADSOPS_DATABASE_USER: adsops
      ADSOPS_DATABASE_PASSWORD: adsops_dev_password
      ADSOPS_DATABASE_DBNAME: adsops_changes
      ADSOPS_DATABASE_SSLMODE: disable
      ADSOPS_REDIS_HOST: redis
      ADSOPS_REDIS_PORT: 6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # hostctl — runs as a long-lived CLI companion pointing at dev postgres
  # Not a server; use `docker compose run hostctl list` or `exec` pattern
  hostctl:
    build:
      context: ../../tools/hostctl
      dockerfile: Dockerfile          # to be created
    container_name: adsops-hostctl
    environment:
      INVENTORY_DB_HOST: postgres
      INVENTORY_DB_PORT: 5432
      INVENTORY_DB_NAME: adsops_changes
      INVENTORY_DB_USER: adsops
      INVENTORY_DB_PASSWORD: adsops_dev_password
    depends_on:
      postgres:
        condition: service_healthy
    # Sleep keeps container alive so you can exec into it
    entrypoint: ["sh", "-c", "while true; do sleep 3600; done"]
    profiles:
      - tools   # opt-in: docker compose --profile tools up

  # statsagent — collects metrics from the local Docker environment
  statsagent:
    build:
      context: ../../tools/statsagent
      dockerfile: deploy/Dockerfile
    container_name: adsops-statsagent
    environment:
      STATSAGENT_PORT: 9100
      STATSAGENT_INTERVAL: 15s
      STATSAGENT_DOCKER_SOCKET: /var/run/docker.sock
    ports:
      - "9100:9100"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    profiles:
      - monitoring

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: adsops-network
```

Design decisions:
- hostctl and statsagent use `profiles` so they do not start with plain `docker compose up` — only opt-in via `--profile tools` or `--profile monitoring`. This keeps the default dev stack lean.
- hostctl uses a sleep-loop entrypoint pattern rather than a CMD because it is a CLI tool, not a server. Use `docker compose exec hostctl hostctl list` or `docker compose run --rm hostctl hostctl list --json`.
- statsagent mounts Docker socket read-only (`:ro`) in compose — sufficient for container listing.
- Do not mount `/proc` in compose for statsagent; process-level stats are not needed in local dev. The DaemonSet mounts `/proc` because real host metrics are the point in production.

---

## Implementation Notes and Sequencing

1. **Confirm `metadata` column type.** Run `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'inventory_resources' AND column_name = 'metadata'` against the inventory DB. If `json`, run the `ALTER COLUMN ... TYPE jsonb` migration before adding JSON path queries. This is the only schema change needed and it is non-destructive.

2. **hostctl changes are additive.** Add `ShowChildren bool` to `ListOptions`, add `printResourceTree` to output.go, wire `--children` flag in commands.go. Existing `--json` output already works correctly for children once infractl writes them.

3. **infractl scan writeback.** Add a `patchMetadata(hostname string, metadata map[string]interface{}) error` function to infractl's inventory package that issues a direct `UPDATE ... SET metadata = $1` query. Do not route through the general `updateResource` path — it rebuilds metadata from opts and will clobber children.

4. **Dockerfile for hostctl.** The CGO/SQLite Dockerfile above is needed only if hostctl retains `mattn/go-sqlite3`. Check `go.mod` in `tools/hostctl/` — if the dependency is `modernc.org/sqlite` (pure Go), use the statsagent Dockerfile pattern verbatim with `CGO_ENABLED=0`.

5. **k3s manifests placement.** Put the DaemonSet YAMLs in `deployments/kubernetes/` alongside the existing `deployment.yaml`. Suggest: `deployments/kubernetes/statsagent-daemonset.yaml` and `deployments/kubernetes/systemapi-agent-daemonset.yaml`.
