#!/usr/bin/env python3
"""
Oracle Cloud Container Management Tool

Manage Oracle Kubernetes Engine (OKE) clusters and Container Instances.
Designed for accessibility with screen reader friendly output.

Usage:
    orccont.py clusters                    # List OKE clusters
    orccont.py cluster <id>                # Show cluster details
    orccont.py containers                  # List container instances
    orccont.py container <id>              # Show container details
    orccont.py create --config cont.json   # Create container instance
    orccont.py delete <id>                 # Delete container instance
    orccont.py logs <id>                   # View container logs
    orccont.py export-config cont.json     # Export config template
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import oci
except ImportError:
    print("Error: OCI Python SDK not installed.")
    print("Install with: pip install oci")
    sys.exit(1)


def speak(message: str):
    """Print message with timestamp for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp for lists and tables."""
    print(message)
    sys.stdout.flush()


def get_oci_config(profile: str = "DEFAULT") -> dict:
    """Load OCI SDK configuration."""
    config_path = Path.home() / ".oci" / "config"
    if not config_path.exists():
        print(f"Error: OCI config not found at {config_path}")
        print("Run 'oci setup config' to create it.")
        sys.exit(1)
    return oci.config.from_file(profile_name=profile)


def format_state(state: str) -> str:
    """Format lifecycle state for readability."""
    states = {
        "RUNNING": "Running",
        "ACTIVE": "Active",
        "CREATING": "Creating",
        "UPDATING": "Updating",
        "DELETED": "Deleted",
        "DELETING": "Deleting",
        "FAILED": "Failed",
        "INACTIVE": "Inactive",
    }
    return states.get(state, state)


def list_clusters(args):
    """List all OKE clusters."""
    speak("Fetching Kubernetes clusters...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]

    try:
        container_engine = oci.container_engine.ContainerEngineClient(config)
        response = container_engine.list_clusters(compartment_id=compartment_id)
        clusters = response.data

        if not clusters:
            speak_plain("")
            speak_plain("No Kubernetes clusters found.")
            speak_plain("Create one in the Oracle Cloud Console or use OCI CLI.")
            return

        speak_plain("")
        speak_plain("Kubernetes (OKE) Clusters")
        speak_plain("=" * 70)
        speak_plain("")

        for cluster in clusters:
            if cluster.lifecycle_state == "DELETED":
                continue

            speak_plain(f"  Name: {cluster.name}")
            speak_plain(f"    ID: {cluster.id}")
            speak_plain(f"    State: {format_state(cluster.lifecycle_state)}")
            speak_plain(f"    Kubernetes Version: {cluster.kubernetes_version}")
            speak_plain(f"    VCN ID: {cluster.vcn_id}")

            if cluster.endpoints:
                if cluster.endpoints.kubernetes:
                    speak_plain(f"    API Endpoint: {cluster.endpoints.kubernetes}")
                if cluster.endpoints.public_endpoint:
                    speak_plain(f"    Public Endpoint: {cluster.endpoints.public_endpoint}")

            speak_plain(f"    Created: {cluster.lifecycle_details or 'N/A'}")
            speak_plain("")

        speak_plain(f"Total: {len([c for c in clusters if c.lifecycle_state != 'DELETED'])} clusters")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_cluster(args):
    """Show detailed cluster information."""
    speak(f"Fetching cluster {args.cluster_id}...")

    config = get_oci_config(args.profile)

    try:
        container_engine = oci.container_engine.ContainerEngineClient(config)
        cluster = container_engine.get_cluster(args.cluster_id).data

        speak_plain("")
        speak_plain("Kubernetes Cluster Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {cluster.name}")
        speak_plain(f"  ID: {cluster.id}")
        speak_plain(f"  State: {format_state(cluster.lifecycle_state)}")
        speak_plain(f"  Kubernetes Version: {cluster.kubernetes_version}")
        speak_plain(f"  Compartment ID: {cluster.compartment_id}")
        speak_plain(f"  VCN ID: {cluster.vcn_id}")

        if cluster.endpoints:
            speak_plain("")
            speak_plain("  Endpoints:")
            if cluster.endpoints.kubernetes:
                speak_plain(f"    API Server: {cluster.endpoints.kubernetes}")
            if cluster.endpoints.public_endpoint:
                speak_plain(f"    Public: {cluster.endpoints.public_endpoint}")
            if cluster.endpoints.private_endpoint:
                speak_plain(f"    Private: {cluster.endpoints.private_endpoint}")

        if cluster.options:
            speak_plain("")
            speak_plain("  Cluster Options:")
            if cluster.options.kubernetes_network_config:
                net = cluster.options.kubernetes_network_config
                speak_plain(f"    Pods CIDR: {net.pods_cidr}")
                speak_plain(f"    Services CIDR: {net.services_cidr}")

        # List node pools
        speak_plain("")
        speak_plain("  Node Pools:")
        pools = container_engine.list_node_pools(
            compartment_id=cluster.compartment_id,
            cluster_id=cluster.id
        ).data

        if pools:
            for pool in pools:
                speak_plain(f"    Pool: {pool.name}")
                speak_plain(f"      ID: {pool.id}")
                speak_plain(f"      Node Shape: {pool.node_shape}")
                speak_plain(f"      Nodes: {pool.node_config_details.size if pool.node_config_details else 'N/A'}")
                speak_plain(f"      State: {format_state(pool.lifecycle_state)}")
                speak_plain("")
        else:
            speak_plain("    No node pools configured.")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_containers(args):
    """List all container instances."""
    speak("Fetching container instances...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]

    try:
        container_instances = oci.container_instances.ContainerInstanceClient(config)
        response = container_instances.list_container_instances(
            compartment_id=compartment_id
        )
        instances = response.data.items

        if not instances:
            speak_plain("")
            speak_plain("No container instances found.")
            speak_plain("Use 'orccont.py create --config cont.json' to create one.")
            return

        speak_plain("")
        speak_plain("Container Instances")
        speak_plain("=" * 70)
        speak_plain("")

        running = 0
        stopped = 0

        for inst in instances:
            if inst.lifecycle_state == "DELETED":
                continue

            speak_plain(f"  Name: {inst.display_name}")
            speak_plain(f"    ID: {inst.id}")
            speak_plain(f"    State: {format_state(inst.lifecycle_state)}")
            speak_plain(f"    Shape: {inst.shape}")
            speak_plain(f"    Containers: {inst.container_count}")
            speak_plain(f"    Created: {inst.time_created.strftime('%Y-%m-%d %H:%M')}")
            speak_plain("")

            if inst.lifecycle_state == "ACTIVE":
                running += 1
            else:
                stopped += 1

        speak_plain(f"Total: {len(instances)} instances ({running} running, {stopped} other)")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_container(args):
    """Show detailed container instance information."""
    speak(f"Fetching container instance {args.container_id}...")

    config = get_oci_config(args.profile)

    try:
        client = oci.container_instances.ContainerInstanceClient(config)
        instance = client.get_container_instance(args.container_id).data

        speak_plain("")
        speak_plain("Container Instance Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {instance.display_name}")
        speak_plain(f"  ID: {instance.id}")
        speak_plain(f"  State: {format_state(instance.lifecycle_state)}")
        speak_plain(f"  Shape: {instance.shape}")

        if instance.shape_config:
            speak_plain(f"  OCPUs: {instance.shape_config.ocpus}")
            speak_plain(f"  Memory: {instance.shape_config.memory_in_gbs} GB")

        speak_plain(f"  Availability Domain: {instance.availability_domain}")
        speak_plain(f"  Created: {instance.time_created.strftime('%Y-%m-%d %H:%M:%S')}")

        # VNIC details
        if instance.vnics:
            speak_plain("")
            speak_plain("  Network:")
            for vnic in instance.vnics:
                if hasattr(vnic, 'private_ip'):
                    speak_plain(f"    Private IP: {vnic.private_ip}")
                if hasattr(vnic, 'public_ip') and vnic.public_ip:
                    speak_plain(f"    Public IP: {vnic.public_ip}")

        # Containers
        speak_plain("")
        speak_plain("  Containers:")
        if instance.containers:
            for container in instance.containers:
                speak_plain(f"    Name: {container.display_name}")
                speak_plain(f"      Image: {container.image_url}")
                speak_plain(f"      State: {format_state(container.lifecycle_state)}")
                if container.command:
                    speak_plain(f"      Command: {' '.join(container.command)}")
                speak_plain("")
        else:
            speak_plain("    No containers in this instance.")

        # Volumes
        if instance.volumes:
            speak_plain("  Volumes:")
            for vol in instance.volumes:
                speak_plain(f"    Name: {vol.name}")
                speak_plain(f"      Type: {vol.volume_type}")
                speak_plain("")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def export_config(args):
    """Export container instance configuration template."""
    template = {
        "_comment": "Container Instance Configuration Template",
        "_instructions": [
            "1. Get compartment_id: orccont.py list-compartments",
            "2. Get subnet_id: orccont.py list-subnets",
            "3. Configure containers with images and commands",
            "4. Run: orccont.py create --config this-file.json"
        ],
        "display_name": "my-container-instance",
        "compartment_id": "ocid1.compartment.oc1..your-compartment-id",
        "availability_domain": "AD-1",
        "shape": "CI.Standard.E4.Flex",
        "shape_config": {
            "ocpus": 1,
            "memory_in_gbs": 4
        },
        "containers": [
            {
                "display_name": "main",
                "image_url": "docker.io/nginx:latest",
                "command": [],
                "arguments": [],
                "environment_variables": {
                    "ENV": "production"
                },
                "resource_config": {
                    "vcpus_limit": 1,
                    "memory_limit_in_gbs": 2
                }
            }
        ],
        "vnics": [
            {
                "subnet_id": "ocid1.subnet.oc1..your-subnet-id",
                "is_public_ip_assigned": True
            }
        ],
        "freeform_tags": {
            "Environment": "development",
            "ManagedBy": "orccont"
        }
    }

    output_path = Path(args.output).expanduser()
    with open(output_path, "w") as f:
        json.dump(template, f, indent=2)

    speak_plain(f"Configuration template saved to: {args.output}")
    speak_plain("")
    speak_plain("Next steps:")
    speak_plain("  1. Edit the file with your settings")
    speak_plain("  2. Run: orccont.py create --config " + args.output)


def create_container(args):
    """Create a new container instance."""
    speak("Loading configuration...")

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    with open(config_path) as f:
        cont_config = json.load(f)

    # Validate required fields
    required = ["display_name", "compartment_id", "shape", "containers", "vnics"]
    for field in required:
        if field not in cont_config:
            print(f"Error: Required field '{field}' missing from config")
            sys.exit(1)

    speak(f"Creating container instance: {cont_config['display_name']}")

    oci_config = get_oci_config(args.profile)
    client = oci.container_instances.ContainerInstanceClient(oci_config)
    identity = oci.identity.IdentityClient(oci_config)

    try:
        # Get availability domain
        ad = cont_config.get("availability_domain", "AD-1")
        if not ad.startswith("ocid"):
            ads = identity.list_availability_domains(cont_config["compartment_id"]).data
            if ad.upper().startswith("AD-"):
                ad_num = int(ad.split("-")[1]) - 1
                if ad_num < len(ads):
                    ad = ads[ad_num].name
                else:
                    ad = ads[0].name
            else:
                ad = ads[0].name

        # Build containers
        containers = []
        for c in cont_config["containers"]:
            container = oci.container_instances.models.CreateContainerDetails(
                display_name=c["display_name"],
                image_url=c["image_url"],
                command=c.get("command"),
                arguments=c.get("arguments"),
                environment_variables=c.get("environment_variables", {})
            )
            if "resource_config" in c:
                container.resource_config = oci.container_instances.models.CreateContainerResourceConfigDetails(
                    vcpus_limit=c["resource_config"].get("vcpus_limit"),
                    memory_limit_in_gbs=c["resource_config"].get("memory_limit_in_gbs")
                )
            containers.append(container)

        # Build VNICs
        vnics = []
        for v in cont_config["vnics"]:
            vnics.append(
                oci.container_instances.models.CreateContainerVnicDetails(
                    subnet_id=v["subnet_id"],
                    is_public_ip_assigned=v.get("is_public_ip_assigned", False)
                )
            )

        # Shape config
        shape_config = None
        if "shape_config" in cont_config:
            shape_config = oci.container_instances.models.CreateContainerInstanceShapeConfigDetails(
                ocpus=float(cont_config["shape_config"].get("ocpus", 1)),
                memory_in_gbs=float(cont_config["shape_config"].get("memory_in_gbs", 4))
            )

        # Create instance details
        create_details = oci.container_instances.models.CreateContainerInstanceDetails(
            display_name=cont_config["display_name"],
            compartment_id=cont_config["compartment_id"],
            availability_domain=ad,
            shape=cont_config["shape"],
            shape_config=shape_config,
            containers=containers,
            vnics=vnics,
            freeform_tags=cont_config.get("freeform_tags", {})
        )

        response = client.create_container_instance(create_details)
        instance = response.data

        speak("Container instance creation initiated!")
        speak_plain("")
        speak_plain(f"  Instance ID: {instance.id}")
        speak_plain(f"  Name: {instance.display_name}")
        speak_plain(f"  State: {format_state(instance.lifecycle_state)}")

        if args.wait:
            speak("Waiting for container instance to be ready...")
            instance = oci.wait_until(
                client,
                client.get_container_instance(instance.id),
                "lifecycle_state",
                "ACTIVE",
                max_wait_seconds=600
            ).data
            speak("Container instance is now running!")
            speak("Use 'orccont.py container " + instance.id + "' to see details")
        else:
            speak("Instance is starting. Use 'orccont.py containers' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def delete_container(args):
    """Delete a container instance."""
    speak(f"WARNING: Deleting container instance {args.container_id}")
    speak("This action cannot be undone!")

    if not args.yes:
        confirm = input("Type 'yes' to confirm deletion: ")
        if confirm.lower() != "yes":
            speak("Deletion cancelled.")
            return

    config = get_oci_config(args.profile)
    client = oci.container_instances.ContainerInstanceClient(config)

    try:
        client.delete_container_instance(args.container_id)
        speak("Deletion initiated successfully.")

        if args.wait:
            speak("Waiting for deletion to complete...")
            oci.wait_until(
                client,
                client.get_container_instance(args.container_id),
                "lifecycle_state",
                "DELETED",
                max_wait_seconds=300,
                succeed_on_not_found=True
            )
            speak("Container instance has been deleted.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def view_logs(args):
    """View container logs."""
    speak(f"Fetching logs for container {args.container_id}...")

    config = get_oci_config(args.profile)
    client = oci.container_instances.ContainerInstanceClient(config)

    try:
        # Get container details to find log location
        response = client.retrieve_logs(
            container_id=args.container_id
        )

        speak_plain("")
        speak_plain("Container Logs")
        speak_plain("=" * 70)
        speak_plain("")

        # Response is a binary stream
        log_content = response.data.content.decode('utf-8', errors='replace')

        if not log_content.strip():
            speak_plain("No logs available yet.")
        else:
            # Limit output if --tail specified
            lines = log_content.split('\n')
            if args.tail and len(lines) > args.tail:
                lines = lines[-args.tail:]
                speak_plain(f"(showing last {args.tail} lines)")
                speak_plain("")

            for line in lines:
                speak_plain(line)

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_subnets(args):
    """List available subnets."""
    speak("Fetching subnets...")

    config = get_oci_config(args.profile)
    network = oci.core.VirtualNetworkClient(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = network.list_subnets(compartment_id=compartment_id)
        subnets = response.data

        if not subnets:
            speak_plain("")
            speak_plain("No subnets found.")
            return

        speak_plain("")
        speak_plain("Available Subnets")
        speak_plain("=" * 70)
        speak_plain("")

        for subnet in subnets:
            speak_plain(f"  Name: {subnet.display_name}")
            speak_plain(f"    ID: {subnet.id}")
            speak_plain(f"    CIDR: {subnet.cidr_block}")
            speak_plain("")

        speak_plain(f"Total: {len(subnets)} subnets")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Cloud Container Management Tool. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    orccont.py clusters                     # List OKE clusters
    orccont.py cluster ocid1.cluster...     # Show cluster details
    orccont.py containers                   # List container instances
    orccont.py container ocid1.container... # Show container details
    orccont.py create --config cont.json    # Create container instance
    orccont.py delete ocid1.container...    # Delete container instance
    orccont.py logs ocid1.container...      # View logs

Screen Reader Notes:
    All output is plain text with clear labels.
    Status messages include timestamps.
    Use --tail N to limit log output.
"""
    )

    parser.add_argument(
        "--profile", "-p",
        default="DEFAULT",
        help="OCI config profile (default: DEFAULT)"
    )
    parser.add_argument(
        "--compartment", "-c",
        help="Compartment OCID (default: tenancy root)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # clusters
    clusters_parser = subparsers.add_parser("clusters", help="List OKE clusters")
    clusters_parser.set_defaults(func=list_clusters)

    # cluster
    cluster_parser = subparsers.add_parser("cluster", help="Show cluster details")
    cluster_parser.add_argument("cluster_id", help="Cluster OCID")
    cluster_parser.set_defaults(func=show_cluster)

    # containers
    containers_parser = subparsers.add_parser("containers", help="List container instances")
    containers_parser.set_defaults(func=list_containers)

    # container
    container_parser = subparsers.add_parser("container", help="Show container details")
    container_parser.add_argument("container_id", help="Container Instance OCID")
    container_parser.set_defaults(func=show_container)

    # create
    create_parser = subparsers.add_parser("create", help="Create container instance")
    create_parser.add_argument("--config", required=True, help="Config file path")
    create_parser.add_argument("--wait", "-w", action="store_true", help="Wait for ready")
    create_parser.set_defaults(func=create_container)

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete container instance")
    delete_parser.add_argument("container_id", help="Container Instance OCID")
    delete_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    delete_parser.add_argument("--wait", "-w", action="store_true", help="Wait for deletion")
    delete_parser.set_defaults(func=delete_container)

    # logs
    logs_parser = subparsers.add_parser("logs", help="View container logs")
    logs_parser.add_argument("container_id", help="Container OCID")
    logs_parser.add_argument("--tail", "-n", type=int, help="Number of lines to show")
    logs_parser.set_defaults(func=view_logs)

    # export-config
    export_parser = subparsers.add_parser("export-config", help="Export config template")
    export_parser.add_argument("output", help="Output file path")
    export_parser.set_defaults(func=export_config)

    # list-subnets
    subnet_parser = subparsers.add_parser("list-subnets", help="List available subnets")
    subnet_parser.set_defaults(func=list_subnets)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
