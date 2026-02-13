#!/usr/bin/env python3
"""
Dockate Discover - Container Discovery and Indexing Tool

Indexes and tracks containers across:
  - OKE (Oracle Kubernetes Engine) clusters
  - Docker hosts (local and remote)
  - OCIR (Oracle Container Image Registry)

Find containers by name, image, host, or type.

Usage:
    dockate-discover.py index                    # Index all containers
    dockate-discover.py search <name>            # Search by container name
    dockate-discover.py find --image nginx       # Find by image
    dockate-discover.py list --type kubernetes   # List by type
    dockate-discover.py show <container-id>      # Show details
    dockate-discover.py hosts                    # List all container hosts
    dockate-discover.py connect <container-id>   # Show connection command
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sqlite3
from dataclasses import dataclass, asdict

try:
    import oci
except ImportError:
    oci = None

# Configuration
INDEX_DIR = Path.home() / ".adsops" / "container-index"
INDEX_DB = INDEX_DIR / "containers.db"
CACHE_DIR = Path.home() / ".container_discovery"
CACHE_FILE = CACHE_DIR / "last_snapshot.json"
CACHE_HISTORY = CACHE_DIR / "history"
CACHE_TTL = 300  # 5 minutes


def speak(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


def ensure_cache_dirs():
    """Ensure cache directories exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_HISTORY.mkdir(parents=True, exist_ok=True)


def load_cache() -> Optional[Dict[str, Any]]:
    """Load previous snapshot from cache."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        speak_plain(f"Warning: Could not load cache: {e}")
        return None


def save_cache(containers: List['Container'], timestamp: datetime):
    """Save current snapshot to cache."""
    ensure_cache_dirs()

    snapshot = {
        "timestamp": timestamp.isoformat(),
        "containers": [c.to_dict() for c in containers]
    }

    # Save current snapshot
    with open(CACHE_FILE, 'w') as f:
        json.dump(snapshot, f, indent=2)

    # Save to history
    history_file = CACHE_HISTORY / f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    with open(history_file, 'w') as f:
        json.dump(snapshot, f, indent=2)

    # Clean old history (keep last 30 days)
    cleanup_old_snapshots()


def cleanup_old_snapshots(days: int = 30):
    """Remove snapshots older than specified days."""
    if not CACHE_HISTORY.exists():
        return

    cutoff = datetime.now() - timedelta(days=days)

    for snapshot_file in CACHE_HISTORY.glob("snapshot_*.json"):
        try:
            # Extract timestamp from filename
            timestamp_str = snapshot_file.stem.replace("snapshot_", "")
            file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if file_time < cutoff:
                snapshot_file.unlink()
        except Exception:
            pass


def compute_diff(old_containers: List[Dict], new_containers: List[Dict]) -> Dict[str, Any]:
    """Compute differences between old and new container states."""
    old_by_id = {c['id']: c for c in old_containers}
    new_by_id = {c['id']: c for c in new_containers}

    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    added = [new_by_id[cid] for cid in (new_ids - old_ids)]
    removed = [old_by_id[cid] for cid in (old_ids - new_ids)]

    # Check for status changes
    changed = []
    for cid in (old_ids & new_ids):
        old_c = old_by_id[cid]
        new_c = new_by_id[cid]

        if old_c['status'] != new_c['status']:
            changed.append({
                'id': cid,
                'name': new_c['name'],
                'old_status': old_c['status'],
                'new_status': new_c['status']
            })

    return {
        'added': added,
        'removed': removed,
        'changed': changed,
        'total_old': len(old_containers),
        'total_new': len(new_containers)
    }


def show_diff(diff: Dict[str, Any], old_timestamp: str):
    """Display diff information."""
    speak_plain("")
    speak_plain("=" * 80)
    speak_plain(f"Changes since last index ({old_timestamp})")
    speak_plain("=" * 80)

    if diff['added']:
        speak_plain("")
        speak_plain(f"✓ Added ({len(diff['added'])} containers):")
        for c in diff['added']:
            speak_plain(f"  + {c['name']} [{c['image']}] on {c['host']}")

    if diff['removed']:
        speak_plain("")
        speak_plain(f"✗ Removed ({len(diff['removed'])} containers):")
        for c in diff['removed']:
            speak_plain(f"  - {c['name']} [{c['image']}] on {c['host']}")

    if diff['changed']:
        speak_plain("")
        speak_plain(f"⟳ Status Changed ({len(diff['changed'])} containers):")
        for c in diff['changed']:
            speak_plain(f"  ~ {c['name']}: {c['old_status']} → {c['new_status']}")

    if not diff['added'] and not diff['removed'] and not diff['changed']:
        speak_plain("")
        speak_plain("  No changes detected")

    speak_plain("")
    speak_plain(f"Total: {diff['total_old']} → {diff['total_new']} containers")
    speak_plain("=" * 80)


@dataclass
class Container:
    """Container information."""
    id: str
    name: str
    image: str
    status: str
    host: str
    host_type: str  # docker, kubernetes, container-instance
    platform: str   # oke, docker, oci-container
    labels: Dict[str, str]
    created: str
    ports: List[str]
    networks: List[str]
    namespace: Optional[str] = None  # For k8s
    node: Optional[str] = None       # For k8s
    pod: Optional[str] = None        # For k8s

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    def matches(self, query: str) -> bool:
        """Check if container matches search query."""
        query = query.lower()
        return (
            query in self.name.lower() or
            query in self.image.lower() or
            query in self.host.lower() or
            query in self.id.lower()
        )


class ContainerIndex:
    """Container index database."""

    def __init__(self, db_path: Path = INDEX_DB):
        """Initialize index."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS containers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                image TEXT NOT NULL,
                status TEXT NOT NULL,
                host TEXT NOT NULL,
                host_type TEXT NOT NULL,
                platform TEXT NOT NULL,
                labels TEXT,
                created TEXT,
                ports TEXT,
                networks TEXT,
                namespace TEXT,
                node TEXT,
                pod TEXT,
                indexed_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_name ON containers(name)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_image ON containers(image)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_host ON containers(host)
        """)
        conn.commit()
        conn.close()

    def add_container(self, container: Container):
        """Add or update container in index."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO containers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            container.id,
            container.name,
            container.image,
            container.status,
            container.host,
            container.host_type,
            container.platform,
            json.dumps(container.labels),
            container.created,
            json.dumps(container.ports),
            json.dumps(container.networks),
            container.namespace,
            container.node,
            container.pod,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def search(self, query: str = "", **filters) -> List[Container]:
        """Search containers."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        sql = "SELECT * FROM containers WHERE 1=1"
        params = []

        if query:
            sql += " AND (name LIKE ? OR image LIKE ? OR host LIKE ? OR id LIKE ?)"
            pattern = f"%{query}%"
            params.extend([pattern, pattern, pattern, pattern])

        if filters.get("host"):
            sql += " AND host = ?"
            params.append(filters["host"])

        if filters.get("type"):
            sql += " AND host_type = ?"
            params.append(filters["type"])

        if filters.get("platform"):
            sql += " AND platform = ?"
            params.append(filters["platform"])

        if filters.get("status"):
            sql += " AND status = ?"
            params.append(filters["status"])

        if filters.get("image"):
            sql += " AND image LIKE ?"
            params.append(f"%{filters['image']}%")

        if filters.get("namespace"):
            sql += " AND namespace = ?"
            params.append(filters["namespace"])

        cursor = conn.execute(sql, params)
        results = []

        for row in cursor:
            results.append(Container(
                id=row["id"],
                name=row["name"],
                image=row["image"],
                status=row["status"],
                host=row["host"],
                host_type=row["host_type"],
                platform=row["platform"],
                labels=json.loads(row["labels"]) if row["labels"] else {},
                created=row["created"],
                ports=json.loads(row["ports"]) if row["ports"] else [],
                networks=json.loads(row["networks"]) if row["networks"] else [],
                namespace=row["namespace"],
                node=row["node"],
                pod=row["pod"]
            ))

        conn.close()
        return results

    def get(self, container_id: str) -> Optional[Container]:
        """Get container by ID."""
        results = self.search()
        for c in results:
            if c.id.startswith(container_id):
                return c
        return None

    def clear(self):
        """Clear all indexed containers."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM containers")
        conn.commit()
        conn.close()

    def get_hosts(self) -> List[Dict[str, Any]]:
        """Get list of all hosts with container counts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT host, host_type, platform, COUNT(*) as count
            FROM containers
            GROUP BY host, host_type, platform
            ORDER BY host
        """)
        results = []
        for row in cursor:
            results.append({
                "host": row[0],
                "type": row[1],
                "platform": row[2],
                "count": row[3]
            })
        conn.close()
        return results

    def get_stats(self) -> Dict[str, int]:
        """Get index statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM containers")
        total = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM containers WHERE status LIKE '%running%'")
        running = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT host) FROM containers")
        hosts = cursor.fetchone()[0]

        conn.close()
        return {
            "total": total,
            "running": running,
            "stopped": total - running,
            "hosts": hosts
        }


class OKEDiscovery:
    """Discover containers in OKE clusters."""

    def __init__(self, profile: str = "DEFAULT"):
        """Initialize OKE discovery."""
        self.profile = profile
        if oci:
            self.config = oci.config.from_file(profile_name=profile)
        else:
            self.config = None

    def discover(self) -> List[Container]:
        """Discover all OKE containers."""
        if not oci:
            speak_plain("Warning: OCI SDK not installed. Skipping OKE discovery.")
            return []

        containers = []

        try:
            ce_client = oci.container_engine.ContainerEngineClient(self.config)
            compartment_id = self.config.get("tenancy")

            # List all clusters
            clusters = ce_client.list_clusters(compartment_id=compartment_id).data

            for cluster in clusters:
                if cluster.lifecycle_state != "ACTIVE":
                    continue

                speak(f"Discovering OKE cluster: {cluster.name}")

                # Get kubeconfig and query pods
                cluster_containers = self._get_cluster_containers(cluster)
                containers.extend(cluster_containers)

        except Exception as e:
            speak_plain(f"Warning: OKE discovery failed: {e}")

        return containers

    def _get_cluster_containers(self, cluster) -> List[Container]:
        """Get containers from a cluster using kubectl."""
        containers = []

        try:
            # Use kubectl to get pods (assuming kubeconfig is set up)
            result = subprocess.run(
                ["kubectl", "get", "pods", "-A", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return containers

            pods_data = json.loads(result.stdout)

            for pod in pods_data.get("items", []):
                metadata = pod.get("metadata", {})
                spec = pod.get("spec", {})
                status = pod.get("status", {})

                for container_spec in spec.get("containers", []):
                    container = Container(
                        id=f"{metadata.get('namespace')}/{metadata.get('name')}/{container_spec.get('name')}",
                        name=container_spec.get("name"),
                        image=container_spec.get("image"),
                        status=status.get("phase", "Unknown"),
                        host=cluster.name,
                        host_type="kubernetes",
                        platform="oke",
                        labels=metadata.get("labels", {}),
                        created=metadata.get("creationTimestamp", ""),
                        ports=[str(p.get("containerPort")) for p in container_spec.get("ports", [])],
                        networks=[],
                        namespace=metadata.get("namespace"),
                        node=spec.get("nodeName"),
                        pod=metadata.get("name")
                    )
                    containers.append(container)

        except Exception as e:
            speak_plain(f"Warning: Failed to get containers from {cluster.name}: {e}")

        return containers


class DockerDiscovery:
    """Discover containers on Docker hosts."""

    def __init__(self, hosts: Optional[List[str]] = None):
        """Initialize Docker discovery."""
        self.hosts = hosts or ["local"]

    def discover(self) -> List[Container]:
        """Discover all Docker containers."""
        containers = []

        for host in self.hosts:
            speak(f"Discovering Docker host: {host}")

            try:
                if host == "local":
                    host_containers = self._discover_local()
                else:
                    host_containers = self._discover_remote(host)

                containers.extend(host_containers)

            except Exception as e:
                speak_plain(f"Warning: Docker discovery failed for {host}: {e}")

        return containers

    def _discover_local(self) -> List[Container]:
        """Discover local Docker containers."""
        containers = []

        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return containers

            # Docker outputs one JSON object per line
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                data = json.loads(line)

                # Get detailed info
                inspect_result = subprocess.run(
                    ["docker", "inspect", data.get("ID")],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if inspect_result.returncode == 0:
                    inspect_data = json.loads(inspect_result.stdout)[0]

                    container = Container(
                        id=data.get("ID"),
                        name=data.get("Names", "").lstrip("/"),
                        image=data.get("Image"),
                        status=data.get("State"),
                        host="localhost",
                        host_type="docker",
                        platform="docker",
                        labels=inspect_data.get("Config", {}).get("Labels", {}) or {},
                        created=inspect_data.get("Created", ""),
                        ports=[p.split("->")[0] for p in data.get("Ports", "").split(", ") if p],
                        networks=list(inspect_data.get("NetworkSettings", {}).get("Networks", {}).keys())
                    )
                    containers.append(container)

        except Exception as e:
            speak_plain(f"Warning: Local Docker discovery failed: {e}")

        return containers

    def _discover_remote(self, host: str) -> List[Container]:
        """Discover containers on remote Docker host via SSH."""
        containers = []

        try:
            # Try to run docker ps via SSH
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", host, "docker", "ps", "-a", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return containers

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                data = json.loads(line)

                container = Container(
                    id=data.get("ID"),
                    name=data.get("Names", "").lstrip("/"),
                    image=data.get("Image"),
                    status=data.get("State"),
                    host=host,
                    host_type="docker",
                    platform="docker",
                    labels={},
                    created=data.get("CreatedAt", ""),
                    ports=[p.split("->")[0] for p in data.get("Ports", "").split(", ") if p],
                    networks=[]
                )
                containers.append(container)

        except Exception as e:
            speak_plain(f"Warning: Remote Docker discovery failed for {host}: {e}")

        return containers


class OCIRDiscovery:
    """Discover images in OCIR."""

    def __init__(self, profile: str = "DEFAULT"):
        """Initialize OCIR discovery."""
        self.profile = profile
        if oci:
            self.config = oci.config.from_file(profile_name=profile)
        else:
            self.config = None

    def discover(self) -> List[Dict[str, Any]]:
        """Discover all OCIR images."""
        if not oci:
            speak_plain("Warning: OCI SDK not installed. Skipping OCIR discovery.")
            return []

        images = []

        try:
            artifacts_client = oci.artifacts.ArtifactsClient(self.config)
            compartment_id = self.config.get("tenancy")

            # List container repositories
            repos = artifacts_client.list_container_repositories(
                compartment_id=compartment_id
            ).data.items

            for repo in repos:
                speak(f"Discovering OCIR repository: {repo.display_name}")

                # List images in repository
                repo_images = artifacts_client.list_container_images(
                    compartment_id=compartment_id,
                    repository_id=repo.id
                ).data.items

                for img in repo_images:
                    images.append({
                        "repository": repo.display_name,
                        "digest": img.digest,
                        "version": img.version,
                        "created": img.time_created.isoformat() if img.time_created else "",
                        "size_mb": round(img.manifest_size_in_bytes / 1024 / 1024, 2) if img.manifest_size_in_bytes else 0
                    })

        except Exception as e:
            speak_plain(f"Warning: OCIR discovery failed: {e}")

        return images


class OCIContainerDiscovery:
    """Discover OCI Container Instances."""

    def __init__(self, profile: str = "DEFAULT"):
        """Initialize OCI Container discovery."""
        self.profile = profile
        if oci:
            self.config = oci.config.from_file(profile_name=profile)
        else:
            self.config = None

    def discover(self) -> List[Container]:
        """Discover all OCI Container Instances."""
        if not oci:
            return []

        containers = []

        try:
            ci_client = oci.container_instances.ContainerInstanceClient(self.config)
            compartment_id = self.config.get("tenancy")

            instances = ci_client.list_container_instances(
                compartment_id=compartment_id
            ).data.items

            for instance in instances:
                if instance.lifecycle_state != "ACTIVE":
                    continue

                speak(f"Discovering OCI Container Instance: {instance.display_name}")

                # Get full details
                full_instance = ci_client.get_container_instance(instance.id).data

                for cont in full_instance.containers:
                    container = Container(
                        id=f"{instance.id}/{cont.display_name}",
                        name=cont.display_name,
                        image=cont.image_url,
                        status=cont.lifecycle_state,
                        host=instance.display_name,
                        host_type="container-instance",
                        platform="oci-container",
                        labels={},
                        created=instance.time_created.isoformat() if instance.time_created else "",
                        ports=[],
                        networks=[]
                    )
                    containers.append(container)

        except Exception as e:
            speak_plain(f"Warning: OCI Container Instance discovery failed: {e}")

        return containers


# Commands

def cmd_index(args):
    """Index all containers."""
    # Load previous cache for diff
    old_cache = load_cache()

    speak("Starting container discovery...")

    index = ContainerIndex()

    # Clear old index
    if args.clear:
        index.clear()
        speak("Cleared existing index")

    all_containers = []

    # Discover OKE
    if not args.skip_oke:
        oke = OKEDiscovery(profile=args.profile)
        oke_containers = oke.discover()
        all_containers.extend(oke_containers)
        speak(f"Found {len(oke_containers)} OKE containers")

    # Discover Docker
    if not args.skip_docker:
        docker_hosts = args.docker_hosts.split(",") if args.docker_hosts else ["local"]
        docker = DockerDiscovery(hosts=docker_hosts)
        docker_containers = docker.discover()
        all_containers.extend(docker_containers)
        speak(f"Found {len(docker_containers)} Docker containers")

    # Discover OCI Container Instances
    if not args.skip_oci_containers:
        oci_cont = OCIContainerDiscovery(profile=args.profile)
        oci_containers = oci_cont.discover()
        all_containers.extend(oci_containers)
        speak(f"Found {len(oci_containers)} OCI Container Instances")

    # Index all containers
    for container in all_containers:
        index.add_container(container)

    stats = index.get_stats()

    # Compute and show diff if we have previous cache
    if old_cache and not args.no_diff:
        diff = compute_diff(old_cache['containers'], [c.to_dict() for c in all_containers])
        show_diff(diff, old_cache['timestamp'])

    # Save current state to cache
    current_time = datetime.now()
    save_cache(all_containers, current_time)

    speak_plain("")
    speak(f"Indexing complete!")
    speak_plain(f"  Total containers: {stats['total']}")
    speak_plain(f"  Running: {stats['running']}")
    speak_plain(f"  Stopped: {stats['stopped']}")
    speak_plain(f"  Hosts: {stats['hosts']}")
    speak_plain("")
    speak_plain(f"  Cache saved to: {CACHE_FILE}")

    # Discover OCIR images
    if not args.skip_ocir:
        speak_plain("")
        speak("Discovering OCIR images...")
        ocir = OCIRDiscovery(profile=args.profile)
        images = ocir.discover()
        speak(f"Found {len(images)} OCIR images")

        # Save to separate file
        ocir_file = INDEX_DIR / "ocir_images.json"
        with open(ocir_file, "w") as f:
            json.dump(images, f, indent=2)


def cmd_search(args):
    """Search containers."""
    index = ContainerIndex()

    results = index.search(
        query=args.query,
        host=args.host,
        type=args.type,
        platform=args.platform,
        status=args.status,
        image=args.image,
        namespace=args.namespace
    )

    if not results:
        speak_plain("No containers found matching criteria.")
        return

    if args.json:
        print(json.dumps([c.to_dict() for c in results], indent=2))
        return

    speak_plain("")
    speak_plain(f"Found {len(results)} container(s)")
    speak_plain("=" * 80)

    for container in results:
        speak_plain("")
        speak_plain(f"  Name: {container.name}")
        speak_plain(f"    ID: {container.id[:16]}...")
        speak_plain(f"    Image: {container.image}")
        speak_plain(f"    Status: {container.status}")
        speak_plain(f"    Host: {container.host} ({container.host_type})")
        speak_plain(f"    Platform: {container.platform}")

        if container.namespace:
            speak_plain(f"    Namespace: {container.namespace}")
        if container.pod:
            speak_plain(f"    Pod: {container.pod}")
        if container.ports:
            speak_plain(f"    Ports: {', '.join(container.ports)}")


def cmd_show(args):
    """Show container details."""
    index = ContainerIndex()
    container = index.get(args.container_id)

    if not container:
        speak_plain(f"Container not found: {args.container_id}")
        return

    if args.json:
        print(json.dumps(container.to_dict(), indent=2))
        return

    speak_plain("")
    speak_plain("Container Details")
    speak_plain("=" * 80)
    speak_plain("")
    speak_plain(f"  Name: {container.name}")
    speak_plain(f"  ID: {container.id}")
    speak_plain(f"  Image: {container.image}")
    speak_plain(f"  Status: {container.status}")
    speak_plain(f"  Host: {container.host}")
    speak_plain(f"  Type: {container.host_type}")
    speak_plain(f"  Platform: {container.platform}")
    speak_plain(f"  Created: {container.created}")

    if container.namespace:
        speak_plain(f"  Namespace: {container.namespace}")
    if container.pod:
        speak_plain(f"  Pod: {container.pod}")
    if container.node:
        speak_plain(f"  Node: {container.node}")

    if container.ports:
        speak_plain(f"  Ports: {', '.join(container.ports)}")

    if container.networks:
        speak_plain(f"  Networks: {', '.join(container.networks)}")

    if container.labels:
        speak_plain("  Labels:")
        for key, value in container.labels.items():
            speak_plain(f"    {key}: {value}")


def cmd_list(args):
    """List containers."""
    index = ContainerIndex()

    filters = {}
    if args.type:
        filters["type"] = args.type
    if args.platform:
        filters["platform"] = args.platform
    if args.status:
        filters["status"] = args.status

    results = index.search(**filters)

    if args.json:
        print(json.dumps([c.to_dict() for c in results], indent=2))
        return

    speak_plain("")
    speak_plain(f"Total: {len(results)} containers")
    speak_plain("=" * 120)
    speak_plain(f"{'NAME':<30} {'IMAGE':<40} {'STATUS':<12} {'HOST':<30}")
    speak_plain("=" * 120)

    for container in results:
        name = container.name[:29]
        image = container.image[:39]
        status = container.status[:11]
        host = f"{container.host} ({container.host_type})"[:29]
        speak_plain(f"{name:<30} {image:<40} {status:<12} {host:<30}")


def cmd_hosts(args):
    """List all container hosts."""
    index = ContainerIndex()
    hosts = index.get_hosts()

    if args.json:
        print(json.dumps(hosts, indent=2))
        return

    speak_plain("")
    speak_plain("Container Hosts")
    speak_plain("=" * 80)
    speak_plain(f"{'HOST':<40} {'TYPE':<20} {'CONTAINERS':<10}")
    speak_plain("=" * 80)

    for host in hosts:
        speak_plain(f"{host['host']:<40} {host['type']:<20} {host['count']:<10}")

    speak_plain("")
    speak_plain(f"Total: {len(hosts)} hosts")


def cmd_connect(args):
    """Show connection command for container."""
    index = ContainerIndex()
    container = index.get(args.container_id)

    if not container:
        speak_plain(f"Container not found: {args.container_id}")
        return

    speak_plain("")
    speak_plain(f"Connection command for: {container.name}")
    speak_plain("=" * 80)
    speak_plain("")

    if container.host_type == "kubernetes":
        cmd = f"kubectl exec -it -n {container.namespace} {container.pod} -c {container.name} -- /bin/sh"
        speak_plain(f"  {cmd}")

    elif container.host_type == "docker":
        if container.host == "localhost":
            cmd = f"docker exec -it {container.id[:12]} /bin/sh"
        else:
            cmd = f"ssh {container.host} 'docker exec -it {container.id[:12]} /bin/sh'"
        speak_plain(f"  {cmd}")

    elif container.host_type == "container-instance":
        speak_plain("  OCI Container Instances don't support exec.")
        speak_plain("  Use logs instead:")
        speak_plain(f"  oci container-instances container list-container-instance {container.id.split('/')[0]}")

    speak_plain("")


def cmd_stats(args):
    """Show index statistics."""
    index = ContainerIndex()
    stats = index.get_stats()

    speak_plain("")
    speak_plain("Container Index Statistics")
    speak_plain("=" * 80)
    speak_plain("")
    speak_plain(f"  Total containers: {stats['total']}")
    speak_plain(f"  Running: {stats['running']}")
    speak_plain(f"  Stopped: {stats['stopped']}")
    speak_plain(f"  Hosts: {stats['hosts']}")
    speak_plain("")

    # OCIR stats
    ocir_file = INDEX_DIR / "ocir_images.json"
    if ocir_file.exists():
        with open(ocir_file) as f:
            images = json.load(f)
        speak_plain(f"  OCIR images: {len(images)}")
        speak_plain("")

    # Cache stats
    if CACHE_FILE.exists():
        cache = load_cache()
        if cache:
            speak_plain(f"  Last snapshot: {cache['timestamp']}")
            speak_plain(f"  Cached containers: {len(cache['containers'])}")
            speak_plain("")


def cmd_diff(args):
    """Show diff between two snapshots."""
    cache = load_cache()

    if not cache:
        speak_plain("No cache found. Run 'index' first.")
        return

    # Get current state
    index = ContainerIndex()
    current_containers = [c.to_dict() for c in index.search()]

    if not current_containers:
        speak_plain("No containers in current index. Run 'index' first.")
        return

    # Compute diff
    diff = compute_diff(cache['containers'], current_containers)
    show_diff(diff, cache['timestamp'])


def cmd_history(args):
    """Show snapshot history."""
    if not CACHE_HISTORY.exists():
        speak_plain("No history found.")
        return

    snapshots = sorted(CACHE_HISTORY.glob("snapshot_*.json"))

    if not snapshots:
        speak_plain("No snapshots in history.")
        return

    speak_plain("")
    speak_plain("Snapshot History")
    speak_plain("=" * 80)
    speak_plain(f"{'TIMESTAMP':<25} {'CONTAINERS':<15} {'FILE':<40}")
    speak_plain("=" * 80)

    for snapshot_file in snapshots:
        try:
            with open(snapshot_file, 'r') as f:
                snapshot = json.load(f)

            timestamp = snapshot['timestamp']
            count = len(snapshot['containers'])
            filename = snapshot_file.name

            speak_plain(f"{timestamp:<25} {count:<15} {filename:<40}")

        except Exception as e:
            speak_plain(f"Error reading {snapshot_file.name}: {e}")

    speak_plain("")
    speak_plain(f"Total: {len(snapshots)} snapshots")
    speak_plain(f"Location: {CACHE_HISTORY}")
    speak_plain("")


def main():
    parser = argparse.ArgumentParser(
        description="Dockate Discover - Container Discovery and Indexing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    dockate-discover.py index                           # Index all containers
    dockate-discover.py index --clear                   # Clear and re-index
    dockate-discover.py search nginx                    # Search by name
    dockate-discover.py search --image nginx            # Search by image
    dockate-discover.py list --type kubernetes          # List k8s containers
    dockate-discover.py list --platform docker          # List Docker containers
    dockate-discover.py show abc123                     # Show container details
    dockate-discover.py hosts                           # List all hosts
    dockate-discover.py connect abc123                  # Show connection command
    dockate-discover.py stats                           # Show statistics
    dockate-discover.py diff                            # Show changes since last index
    dockate-discover.py history                         # Show snapshot history

Platforms:
    - oke: Oracle Kubernetes Engine
    - docker: Docker hosts (local or remote)
    - oci-container: OCI Container Instances
    - ocir: Oracle Container Image Registry (images only)

Storage Locations:
    ~/.adsops/container-index/       # SQLite index
    ~/.container_discovery/          # Snapshots and diffs
"""
    )

    parser.add_argument("--profile", "-p", default="DEFAULT",
                       help="OCI config profile")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # index
    index_parser = subparsers.add_parser("index", help="Index all containers")
    index_parser.add_argument("--clear", "-c", action="store_true",
                             help="Clear existing index first")
    index_parser.add_argument("--no-diff", action="store_true",
                             help="Don't show diff from previous index")
    index_parser.add_argument("--skip-oke", action="store_true",
                             help="Skip OKE discovery")
    index_parser.add_argument("--skip-docker", action="store_true",
                             help="Skip Docker discovery")
    index_parser.add_argument("--skip-oci-containers", action="store_true",
                             help="Skip OCI Container Instances")
    index_parser.add_argument("--skip-ocir", action="store_true",
                             help="Skip OCIR image discovery")
    index_parser.add_argument("--docker-hosts", "-d",
                             help="Comma-separated list of Docker hosts (default: local)")
    index_parser.set_defaults(func=cmd_index)

    # search
    search_parser = subparsers.add_parser("search", help="Search containers")
    search_parser.add_argument("query", nargs="?", default="",
                              help="Search query")
    search_parser.add_argument("--host", help="Filter by host")
    search_parser.add_argument("--type", help="Filter by type (docker, kubernetes)")
    search_parser.add_argument("--platform", help="Filter by platform (oke, docker, oci-container)")
    search_parser.add_argument("--status", help="Filter by status")
    search_parser.add_argument("--image", help="Filter by image name")
    search_parser.add_argument("--namespace", "-n", help="Filter by namespace (k8s)")
    search_parser.set_defaults(func=cmd_search)

    # show
    show_parser = subparsers.add_parser("show", help="Show container details")
    show_parser.add_argument("container_id", help="Container ID (or prefix)")
    show_parser.set_defaults(func=cmd_show)

    # list
    list_parser = subparsers.add_parser("list", help="List containers")
    list_parser.add_argument("--type", help="Filter by type")
    list_parser.add_argument("--platform", help="Filter by platform")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.set_defaults(func=cmd_list)

    # hosts
    hosts_parser = subparsers.add_parser("hosts", help="List container hosts")
    hosts_parser.set_defaults(func=cmd_hosts)

    # connect
    connect_parser = subparsers.add_parser("connect", help="Show connection command")
    connect_parser.add_argument("container_id", help="Container ID (or prefix)")
    connect_parser.set_defaults(func=cmd_connect)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # diff
    diff_parser = subparsers.add_parser("diff", help="Show changes since last index")
    diff_parser.set_defaults(func=cmd_diff)

    # history
    history_parser = subparsers.add_parser("history", help="Show snapshot history")
    history_parser.set_defaults(func=cmd_history)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        speak("")
        speak("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
