# Dockate Discover

Container Discovery and Indexing Tool for OKE, Docker, and OCIR.

## Overview

`dockate-discover.py` is a comprehensive tool that indexes and tracks containers across multiple platforms:

- **OKE (Oracle Kubernetes Engine)**: Discovers pods and containers in OKE clusters
- **Docker**: Discovers containers on local and remote Docker hosts
- **OCI Container Instances**: Discovers OCI-managed container instances
- **OCIR (Oracle Container Image Registry)**: Indexes container images

## Features

- Fast SQLite-based indexing for instant searches
- Search by container name, image, host, or platform
- Filter by status (running/stopped), type (docker/kubernetes), or platform
- Shows connection commands for accessing containers
- Supports multiple Docker hosts via SSH
- JSON output for scripting and automation

## Installation

```bash
# Make executable
chmod +x tools/dockate-discover.py

# Optional: Create symlink for easy access
ln -s "$(pwd)/tools/dockate-discover.py" /usr/local/bin/dockate-discover
```

## Requirements

- Python 3.7+
- OCI Python SDK (for OKE/OCIR): `pip install oci`
- Docker (for local container discovery)
- kubectl (for OKE cluster access)
- SSH access to remote Docker hosts (optional)

## Quick Start

### 1. Index All Containers

```bash
# Index everything (shows diff from last run)
./tools/dockate-discover.py index

# Index only local Docker containers
./tools/dockate-discover.py index --skip-oke --skip-oci-containers --skip-ocir

# Clear and re-index
./tools/dockate-discover.py index --clear

# Index without showing diff
./tools/dockate-discover.py index --no-diff
```

**Note:** On first run, a cache file is created in `~/.container_discovery/` to track changes between runs.

### 2. Search for Containers

```bash
# Search by name
./tools/dockate-discover.py search nginx

# Search by image
./tools/dockate-discover.py search --image redis

# Search in specific namespace (k8s)
./tools/dockate-discover.py search --namespace production
```

### 3. List Containers

```bash
# List all containers
./tools/dockate-discover.py list

# List only Kubernetes containers
./tools/dockate-discover.py list --type kubernetes

# List only Docker containers
./tools/dockate-discover.py list --type docker

# List by platform
./tools/dockate-discover.py list --platform oke
```

### 4. Show Container Details

```bash
# Show full details (use container ID or prefix)
./tools/dockate-discover.py show abc123

# Get JSON output
./tools/dockate-discover.py show abc123 --json
```

### 5. Get Connection Command

```bash
# Shows the appropriate command to connect/exec into container
./tools/dockate-discover.py connect abc123

# For k8s: kubectl exec -it -n namespace pod -c container -- /bin/sh
# For Docker: docker exec -it container_id /bin/sh
```

### 6. List All Hosts

```bash
# Show all container hosts with counts
./tools/dockate-discover.py hosts
```

### 7. View Statistics

```bash
# Show index statistics (includes cache info)
./tools/dockate-discover.py stats
```

### 8. View Changes (Diff)

```bash
# Show what changed since last index
./tools/dockate-discover.py diff
```

Shows:
- ✓ Added containers
- ✗ Removed containers
- ⟳ Status changes (running → stopped, etc.)

### 9. View Snapshot History

```bash
# List all historical snapshots
./tools/dockate-discover.py history
```

Shows all saved snapshots with timestamps and container counts.

## Usage Examples

### Typical Workflow with Change Tracking

```bash
# First run - creates initial snapshot
./tools/dockate-discover.py index
# Output: Creates cache in ~/.container_discovery/

# Later - deploy new containers
docker run -d --name nginx nginx:latest
kubectl apply -f deployment.yaml

# Re-index to see what changed
./tools/dockate-discover.py index
# Output:
# ================================================================================
# Changes since last index (2026-02-13T12:00:00.000000)
# ================================================================================
#
# ✓ Added (2 containers):
#   + nginx [nginx:latest] on localhost
#   + myapp [myapp:v1.2] on my-cluster
#
# Total: 10 → 12 containers
# ================================================================================

# View all historical snapshots
./tools/dockate-discover.py history

# Check current diff without re-indexing
./tools/dockate-discover.py diff
```

### Index Remote Docker Hosts

```bash
# Specify remote Docker hosts (comma-separated)
./tools/dockate-discover.py index --docker-hosts "host1.example.com,host2.example.com"
```

### Search Workflow

```bash
# Find all nginx containers
./tools/dockate-discover.py search nginx

# Find containers on specific host
./tools/dockate-discover.py search --host my-cluster

# Find running containers only
./tools/dockate-discover.py search --status running

# Get JSON for scripting
./tools/dockate-discover.py search nginx --json | jq '.[] | .name'
```

### Platform-Specific Queries

```bash
# All OKE containers
./tools/dockate-discover.py list --platform oke

# All Docker containers
./tools/dockate-discover.py list --platform docker

# All OCI Container Instances
./tools/dockate-discover.py list --platform oci-container
```

## Configuration

### OCI Profile

Use a different OCI config profile:

```bash
./tools/dockate-discover.py index --profile MYPROFILE
```

### Docker Hosts

By default, only local Docker is discovered. To add remote hosts:

```bash
# Via command line
./tools/dockate-discover.py index --docker-hosts "host1,host2,host3"

# Or set in environment
export DOCKATE_DOCKER_HOSTS="host1.example.com,host2.example.com"
```

## Index Storage

### SQLite Index

Location: `~/.adsops/container-index/`

- `containers.db` - SQLite database with indexed containers
- `ocir_images.json` - OCIR image registry data

### Snapshot Cache

Location: `~/.container_discovery/`

- `last_snapshot.json` - Most recent snapshot for quick diff
- `history/snapshot_*.json` - Historical snapshots (30 day retention)

The cache system automatically:
- Creates a snapshot on each index run
- Compares with previous snapshot to show changes
- Stores history for trend analysis
- Cleans up snapshots older than 30 days

## Container Information

Each indexed container includes:

- **Basic Info**: ID, name, image, status
- **Location**: host, platform, type
- **Kubernetes**: namespace, pod, node (if applicable)
- **Networking**: ports, networks
- **Metadata**: labels, creation time

## Platform Types

### Host Types

- `docker` - Standard Docker containers
- `kubernetes` - Kubernetes pods/containers
- `container-instance` - OCI Container Instances

### Platforms

- `oke` - Oracle Kubernetes Engine
- `docker` - Docker hosts (local or remote)
- `oci-container` - OCI Container Instances
- `ocir` - Oracle Container Image Registry

## Advanced Usage

### Filtering

Combine multiple filters:

```bash
./tools/dockate-discover.py search \
  --type kubernetes \
  --namespace production \
  --status Running \
  --image nginx
```

### JSON Output for Automation

```bash
# Get all running containers as JSON
./tools/dockate-discover.py list --status running --json

# Extract specific fields with jq
./tools/dockate-discover.py search nginx --json | \
  jq -r '.[] | "\(.name) on \(.host)"'

# Count containers by platform
./tools/dockate-discover.py list --json | \
  jq 'group_by(.platform) | map({platform: .[0].platform, count: length})'
```

### Scheduled Indexing

Set up a cron job to keep the index fresh:

```bash
# Add to crontab
*/15 * * * * /path/to/dockate-discover.py index --clear >/dev/null 2>&1
```

## Cache Management

### Clear Cache

To reset the snapshot history:

```bash
# Remove all snapshots
rm -rf ~/.container_discovery/

# Next index will create fresh cache
./tools/dockate-discover.py index
```

### Manual Snapshot Analysis

Snapshots are JSON files that can be analyzed with jq:

```bash
# View latest snapshot
cat ~/.container_discovery/last_snapshot.json | jq '.'

# Count containers in a historical snapshot
cat ~/.container_discovery/history/snapshot_20260213_120000.json | jq '.containers | length'

# Extract container names from snapshot
cat ~/.container_discovery/last_snapshot.json | jq -r '.containers[].name'
```

## Troubleshooting

### OCI SDK Not Found

```bash
pip install oci
```

### kubectl Not Configured

Ensure you have kubeconfig set up for your OKE clusters:

```bash
oci ce cluster create-kubeconfig --cluster-id <cluster-id>
export KUBECONFIG=~/.kube/config
```

### Remote Docker Host Access

Ensure SSH access to remote Docker hosts:

```bash
# Test SSH access
ssh user@docker-host docker ps

# Ensure Docker socket permissions
ssh user@docker-host sudo usermod -aG docker $USER
```

### Empty Index

If indexing returns 0 containers:

1. Check that services are running (Docker, kubectl)
2. Verify OCI credentials: `oci iam user get --user-id <user-id>`
3. Check kubectl context: `kubectl config current-context`
4. Run with `DEBUG=1` for verbose output:

```bash
DEBUG=1 ./tools/dockate-discover.py index
```

## Integration with Other Tools

### With adsops-discover

Combine with the OCI resource discovery tool:

```bash
# Find container host details
./tools/adsops-discover access $(./tools/dockate-discover.py show <id> --json | jq -r '.host')
```

### With Docker

```bash
# Get container ID and exec directly
CONTAINER_ID=$(./tools/dockate-discover.py search myapp --json | jq -r '.[0].id')
docker exec -it $CONTAINER_ID /bin/sh
```

### With kubectl

```bash
# Get pod details for k8s containers
./tools/dockate-discover.py search --type kubernetes myapp --json | \
  jq -r '.[] | "kubectl get pod \(.pod) -n \(.namespace)"' | \
  sh
```

## Performance

- Initial indexing: ~10-30 seconds (depends on number of clusters/hosts)
- Search queries: <100ms (SQLite indexed)
- Recommended re-index interval: Every 5-15 minutes

## Security

- Index stored in user home directory (`~/.adsops/`)
- No credentials stored (uses OCI SDK config)
- Remote Docker access via SSH (uses your SSH keys)
- Read-only operations (no container modifications)

## Contributing

Found a bug or want a feature? Open an issue or submit a PR!

## License

Part of the adsops-utils toolkit.
