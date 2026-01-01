#!/usr/bin/env python3
"""
Cloud Top - Multi-Cloud Resource Monitor

Monitor resources across multiple cloud providers.
Python version of cloudtop, designed for accessibility.

Usage:
    cloudtop.py --all                      # Show all providers
    cloudtop.py --oracle                   # Oracle Cloud only
    cloudtop.py --cloudflare               # Cloudflare only
    cloudtop.py --neon                     # Neon databases
    cloudtop.py --running                  # Running resources only
    cloudtop.py --json                     # JSON output
    cloudtop.py --refresh 30               # Auto-refresh every 30s
    cloudtop.py init                       # Generate config file
"""

import argparse
import json
import os
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration file location
CONFIG_PATH = Path.home() / ".cloudtop.json"


def speak(message: str):
    """Print message with timestamp for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


class Resource:
    """Represents a cloud resource."""
    def __init__(self, name: str, resource_type: str, status: str,
                 region: str = "", provider: str = "", **kwargs):
        self.name = name
        self.type = resource_type
        self.status = status
        self.region = region
        self.provider = provider
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "region": self.region,
            "provider": self.provider,
            **self.extra
        }


class Provider(ABC):
    """Base class for cloud providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def initialize(self, config: dict) -> bool:
        pass

    @abstractmethod
    def list_resources(self, filters: dict = None) -> List[Resource]:
        pass

    def close(self):
        pass


class OracleProvider(Provider):
    """Oracle Cloud Infrastructure provider."""

    @property
    def name(self) -> str:
        return "oracle"

    def initialize(self, config: dict) -> bool:
        try:
            import oci
            profile = config.get("profile", "DEFAULT")
            self.oci_config = oci.config.from_file(profile_name=profile)
            self.compute_client = oci.core.ComputeClient(self.oci_config)
            self.compartment_id = config.get("compartment_id") or self.oci_config["tenancy"]
            return True
        except Exception as e:
            speak(f"Oracle Cloud init failed: {e}")
            return False

    def list_resources(self, filters: dict = None) -> List[Resource]:
        resources = []
        filters = filters or {}

        try:
            instances = self.compute_client.list_instances(
                compartment_id=self.compartment_id
            ).data

            for inst in instances:
                if inst.lifecycle_state == "TERMINATED":
                    continue

                if filters.get("running") and inst.lifecycle_state != "RUNNING":
                    continue

                resources.append(Resource(
                    name=inst.display_name,
                    resource_type="compute",
                    status=inst.lifecycle_state.lower(),
                    region=inst.region,
                    provider=self.name,
                    shape=inst.shape,
                    ocpus=inst.shape_config.ocpus if inst.shape_config else None,
                    memory_gb=inst.shape_config.memory_in_gbs if inst.shape_config else None
                ))

        except Exception as e:
            speak(f"Oracle error: {e}")

        return resources


class CloudflareProvider(Provider):
    """Cloudflare provider."""

    @property
    def name(self) -> str:
        return "cloudflare"

    def initialize(self, config: dict) -> bool:
        try:
            import requests
            self.session = requests.Session()
            self.api_token = config.get("api_token") or os.environ.get("CLOUDFLARE_API_TOKEN")
            self.account_id = config.get("account_id") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")

            if not self.api_token:
                speak("Cloudflare: No API token configured")
                return False

            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            })
            return True
        except Exception as e:
            speak(f"Cloudflare init failed: {e}")
            return False

    def list_resources(self, filters: dict = None) -> List[Resource]:
        resources = []
        filters = filters or {}

        try:
            # List Workers
            if self.account_id:
                response = self.session.get(
                    f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/workers/scripts"
                )
                if response.ok:
                    data = response.json()
                    for worker in data.get("result", []):
                        resources.append(Resource(
                            name=worker.get("id", "unknown"),
                            resource_type="workers",
                            status="active",
                            region="global",
                            provider=self.name
                        ))

                # List R2 buckets
                response = self.session.get(
                    f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/r2/buckets"
                )
                if response.ok:
                    data = response.json()
                    for bucket in data.get("result", {}).get("buckets", []):
                        resources.append(Resource(
                            name=bucket.get("name", "unknown"),
                            resource_type="r2",
                            status="active",
                            region="global",
                            provider=self.name
                        ))

        except Exception as e:
            speak(f"Cloudflare error: {e}")

        return resources


class NeonProvider(Provider):
    """Neon serverless Postgres provider."""

    @property
    def name(self) -> str:
        return "neon"

    def initialize(self, config: dict) -> bool:
        try:
            import requests
            self.session = requests.Session()
            self.api_key = config.get("api_key") or os.environ.get("NEON_API_KEY")

            if not self.api_key:
                speak("Neon: No API key configured")
                return False

            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
            return True
        except Exception as e:
            speak(f"Neon init failed: {e}")
            return False

    def list_resources(self, filters: dict = None) -> List[Resource]:
        resources = []
        filters = filters or {}

        try:
            response = self.session.get("https://console.neon.tech/api/v2/projects")
            if response.ok:
                data = response.json()
                for project in data.get("projects", []):
                    status = "active" if project.get("active_time_seconds", 0) > 0 else "idle"

                    if filters.get("running") and status != "active":
                        continue

                    resources.append(Resource(
                        name=project.get("name", "unknown"),
                        resource_type="postgres",
                        status=status,
                        region=project.get("region_id", "unknown"),
                        provider=self.name,
                        pg_version=project.get("pg_version")
                    ))

        except Exception as e:
            speak(f"Neon error: {e}")

        return resources


class VastAIProvider(Provider):
    """Vast.ai GPU provider."""

    @property
    def name(self) -> str:
        return "vastai"

    def initialize(self, config: dict) -> bool:
        try:
            import requests
            self.session = requests.Session()
            self.api_key = config.get("api_key") or os.environ.get("VASTAI_API_KEY")

            if not self.api_key:
                speak("Vast.ai: No API key configured")
                return False

            self.session.headers.update({
                "Accept": "application/json"
            })
            return True
        except Exception as e:
            speak(f"Vast.ai init failed: {e}")
            return False

    def list_resources(self, filters: dict = None) -> List[Resource]:
        resources = []
        filters = filters or {}

        try:
            response = self.session.get(
                "https://console.vast.ai/api/v0/instances/",
                params={"api_key": self.api_key}
            )
            if response.ok:
                data = response.json()
                for instance in data.get("instances", []):
                    status = instance.get("actual_status", "unknown")

                    if filters.get("running") and status != "running":
                        continue

                    resources.append(Resource(
                        name=f"instance-{instance.get('id')}",
                        resource_type="gpu",
                        status=status,
                        region=instance.get("geolocation", "unknown"),
                        provider=self.name,
                        gpu_name=instance.get("gpu_name"),
                        num_gpus=instance.get("num_gpus"),
                        dph_total=instance.get("dph_total")
                    ))

        except Exception as e:
            speak(f"Vast.ai error: {e}")

        return resources


class RunPodProvider(Provider):
    """RunPod GPU provider."""

    @property
    def name(self) -> str:
        return "runpod"

    def initialize(self, config: dict) -> bool:
        try:
            import requests
            self.session = requests.Session()
            self.api_key = config.get("api_key") or os.environ.get("RUNPOD_API_KEY")

            if not self.api_key:
                speak("RunPod: No API key configured")
                return False

            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
            return True
        except Exception as e:
            speak(f"RunPod init failed: {e}")
            return False

    def list_resources(self, filters: dict = None) -> List[Resource]:
        resources = []
        filters = filters or {}

        try:
            # GraphQL query for pods
            query = """
            query {
                myself {
                    pods {
                        id
                        name
                        desiredStatus
                        runtime {
                            gpuCount
                        }
                        machine {
                            gpuDisplayName
                        }
                    }
                }
            }
            """
            response = self.session.post(
                "https://api.runpod.io/graphql",
                json={"query": query}
            )
            if response.ok:
                data = response.json()
                pods = data.get("data", {}).get("myself", {}).get("pods", [])

                for pod in pods:
                    status = pod.get("desiredStatus", "unknown").lower()

                    if filters.get("running") and status != "running":
                        continue

                    resources.append(Resource(
                        name=pod.get("name") or f"pod-{pod.get('id')}",
                        resource_type="gpu",
                        status=status,
                        region="global",
                        provider=self.name,
                        gpu_name=pod.get("machine", {}).get("gpuDisplayName"),
                        num_gpus=pod.get("runtime", {}).get("gpuCount")
                    ))

        except Exception as e:
            speak(f"RunPod error: {e}")

        return resources


def load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_sample_config():
    """Save sample configuration file."""
    sample = {
        "_comment": "cloudtop configuration file",
        "providers": {
            "oracle": {
                "enabled": True,
                "profile": "DEFAULT",
                "compartment_id": ""
            },
            "cloudflare": {
                "enabled": False,
                "api_token": "",
                "account_id": ""
            },
            "neon": {
                "enabled": False,
                "api_key": ""
            },
            "vastai": {
                "enabled": False,
                "api_key": ""
            },
            "runpod": {
                "enabled": False,
                "api_key": ""
            }
        },
        "defaults": {
            "output_format": "table",
            "show_all": True
        }
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(sample, f, indent=2)

    speak_plain(f"Configuration file created: {CONFIG_PATH}")
    speak_plain("")
    speak_plain("Edit this file to configure your cloud providers.")
    speak_plain("You can also use environment variables:")
    speak_plain("  CLOUDFLARE_API_TOKEN, NEON_API_KEY, VASTAI_API_KEY, RUNPOD_API_KEY")


def format_table(resources: List[Resource], wide: bool = False):
    """Format resources as a table."""
    if not resources:
        speak_plain("No resources found.")
        return

    # Group by provider
    by_provider: Dict[str, List[Resource]] = {}
    for r in resources:
        if r.provider not in by_provider:
            by_provider[r.provider] = []
        by_provider[r.provider].append(r)

    for provider, provider_resources in by_provider.items():
        speak_plain("")
        speak_plain(f"=== {provider.upper()} " + "=" * (60 - len(provider)))
        speak_plain("")

        if wide:
            speak_plain(f"{'NAME':<30} {'TYPE':<15} {'REGION':<15} {'STATUS':<10} {'DETAILS'}")
            speak_plain("-" * 90)
        else:
            speak_plain(f"{'NAME':<30} {'TYPE':<15} {'REGION':<15} {'STATUS':<10}")
            speak_plain("-" * 70)

        for r in provider_resources:
            details = ""
            if wide:
                if r.extra.get("shape"):
                    details = f"shape={r.extra['shape']}"
                if r.extra.get("gpu_name"):
                    details = f"gpu={r.extra['gpu_name']}"
                if r.extra.get("pg_version"):
                    details = f"pg={r.extra['pg_version']}"

            name = r.name[:28] + ".." if len(r.name) > 30 else r.name
            region = r.region[:13] + ".." if len(r.region) > 15 else r.region

            if wide:
                speak_plain(f"{name:<30} {r.type:<15} {region:<15} {r.status:<10} {details}")
            else:
                speak_plain(f"{name:<30} {r.type:<15} {region:<15} {r.status:<10}")

    speak_plain("")
    speak_plain(f"Total: {len(resources)} resources")


def format_json(resources: List[Resource]):
    """Format resources as JSON."""
    output = {
        "resources": [r.to_dict() for r in resources],
        "total": len(resources),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    print(json.dumps(output, indent=2))


def run_collection(args, config: dict):
    """Run resource collection."""
    providers_to_use = []

    # Available providers
    all_providers = {
        "oracle": OracleProvider,
        "cloudflare": CloudflareProvider,
        "neon": NeonProvider,
        "vastai": VastAIProvider,
        "runpod": RunPodProvider,
    }

    # Determine which providers to use
    if args.all:
        providers_to_use = list(all_providers.keys())
    else:
        if args.oracle:
            providers_to_use.append("oracle")
        if args.cloudflare:
            providers_to_use.append("cloudflare")
        if args.neon:
            providers_to_use.append("neon")
        if args.vastai:
            providers_to_use.append("vastai")
        if args.runpod:
            providers_to_use.append("runpod")

    # Default to all enabled providers if none specified
    if not providers_to_use:
        provider_configs = config.get("providers", {})
        for name, pconfig in provider_configs.items():
            if pconfig.get("enabled", False):
                providers_to_use.append(name)

    if not providers_to_use:
        speak_plain("No providers configured. Run 'cloudtop.py init' to create config.")
        return []

    # Initialize providers
    active_providers = []
    provider_configs = config.get("providers", {})

    for name in providers_to_use:
        if name not in all_providers:
            continue

        pconfig = provider_configs.get(name, {})
        provider = all_providers[name]()

        if provider.initialize(pconfig):
            active_providers.append(provider)

    if not active_providers:
        speak_plain("No providers could be initialized.")
        return []

    # Collect resources
    filters = {"running": args.running}
    all_resources = []

    speak(f"Collecting from {len(active_providers)} providers...")

    with ThreadPoolExecutor(max_workers=len(active_providers)) as executor:
        futures = {
            executor.submit(p.list_resources, filters): p
            for p in active_providers
        }

        for future in as_completed(futures):
            try:
                resources = future.result()
                all_resources.extend(resources)
            except Exception as e:
                provider = futures[future]
                speak(f"Error from {provider.name}: {e}")

    # Cleanup
    for p in active_providers:
        p.close()

    return all_resources


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Top - Multi-Cloud Resource Monitor. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    cloudtop.py --all                    # Show all providers
    cloudtop.py --oracle                 # Oracle Cloud only
    cloudtop.py --cloudflare             # Cloudflare only
    cloudtop.py --neon                   # Neon databases
    cloudtop.py --running                # Running resources only
    cloudtop.py --json                   # JSON output
    cloudtop.py --wide                   # Wide table with details
    cloudtop.py --refresh 30             # Auto-refresh every 30s
    cloudtop.py init                     # Generate config file

Environment Variables:
    CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
    NEON_API_KEY
    VASTAI_API_KEY
    RUNPOD_API_KEY

Screen Reader Notes:
    Resources are grouped by provider.
    Each resource shows name, type, region, and status.
    Use --wide for additional details.
"""
    )

    # Provider flags
    parser.add_argument("--oracle", "-o", action="store_true", help="Oracle Cloud")
    parser.add_argument("--cloudflare", "-c", action="store_true", help="Cloudflare")
    parser.add_argument("--neon", "-n", action="store_true", help="Neon databases")
    parser.add_argument("--vastai", action="store_true", help="Vast.ai GPU")
    parser.add_argument("--runpod", action="store_true", help="RunPod GPU")
    parser.add_argument("--all", "-a", action="store_true", help="All providers")

    # Filter flags
    parser.add_argument("--running", "-r", action="store_true", help="Running only")

    # Output flags
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--wide", "-w", action="store_true", help="Wide table")
    parser.add_argument("--refresh", type=int, metavar="SECONDS", help="Auto-refresh")

    # Commands
    parser.add_argument("command", nargs="?", help="Command (init)")

    args = parser.parse_args()

    # Handle init command
    if args.command == "init":
        save_sample_config()
        return

    # Load config
    config = load_config()

    try:
        if args.refresh:
            # Continuous mode
            while True:
                # Clear screen (accessible way)
                speak_plain("\n" * 3)
                speak(f"cloudtop - refreshing every {args.refresh}s (Ctrl+C to quit)")

                resources = run_collection(args, config)

                if args.json:
                    format_json(resources)
                else:
                    format_table(resources, args.wide)

                time.sleep(args.refresh)
        else:
            # Single run
            resources = run_collection(args, config)

            if args.json:
                format_json(resources)
            else:
                format_table(resources, args.wide)

    except KeyboardInterrupt:
        speak("")
        speak("Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
