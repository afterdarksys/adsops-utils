#!/usr/bin/env python3
"""
Oracle Cloud VM Management Tool

Manage Oracle Cloud Infrastructure virtual machines with accessibility in mind.
Designed for screen reader users with clear, plain text output.

Usage:
    orcvm.py list                     # List all VMs
    orcvm.py show <instance-id>       # Show VM details
    orcvm.py create --config vm.json  # Create VM from config
    orcvm.py start <instance-id>      # Start a stopped VM
    orcvm.py stop <instance-id>       # Stop a running VM
    orcvm.py terminate <instance-id>  # Terminate VM (permanent)
    orcvm.py images                   # List available OS images
    orcvm.py shapes                   # List available shapes
    orcvm.py export-config vm.json    # Export config template
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import oci
except ImportError:
    print("Error: OCI Python SDK not installed.")
    print("Install with: pip install oci")
    sys.exit(1)


# Common operating systems with their identifiers
OPERATING_SYSTEMS = [
    {"name": "Oracle Linux", "os": "Oracle Linux", "default_version": "9"},
    {"name": "Ubuntu", "os": "Canonical Ubuntu", "default_version": "22.04"},
    {"name": "CentOS", "os": "CentOS", "default_version": "8"},
    {"name": "Rocky Linux", "os": "Rocky Linux", "default_version": "9"},
    {"name": "Alma Linux", "os": "Alma Linux", "default_version": "9"},
    {"name": "Windows Server", "os": "Windows", "default_version": "2022"},
]


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


def get_clients(config: dict) -> tuple:
    """Initialize OCI clients."""
    compute = oci.core.ComputeClient(config)
    identity = oci.identity.IdentityClient(config)
    network = oci.core.VirtualNetworkClient(config)
    return compute, identity, network


def format_state(state: str) -> str:
    """Format lifecycle state for readability."""
    states = {
        "RUNNING": "Running",
        "STOPPED": "Stopped",
        "STOPPING": "Stopping",
        "STARTING": "Starting",
        "TERMINATED": "Terminated",
        "TERMINATING": "Terminating",
        "PROVISIONING": "Provisioning",
    }
    return states.get(state, state)


def list_vms(args):
    """List all virtual machines."""
    speak("Fetching virtual machines...")

    config = get_oci_config(args.profile)
    compute, identity, _ = get_clients(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = compute.list_instances(compartment_id=compartment_id)
        instances = response.data

        if not instances:
            speak_plain("")
            speak_plain("No virtual machines found.")
            speak_plain("Use 'orcvm.py create --config vm.json' to create one.")
            return

        speak_plain("")
        speak_plain("Virtual Machines")
        speak_plain("=" * 70)
        speak_plain("")

        running = 0
        stopped = 0

        for vm in instances:
            if vm.lifecycle_state == "TERMINATED":
                continue

            speak_plain(f"  Name: {vm.display_name}")
            speak_plain(f"    ID: {vm.id}")
            speak_plain(f"    State: {format_state(vm.lifecycle_state)}")
            speak_plain(f"    Shape: {vm.shape}")
            speak_plain(f"    Region: {vm.region}")
            speak_plain(f"    Created: {vm.time_created.strftime('%Y-%m-%d %H:%M')}")

            if vm.shape_config:
                speak_plain(f"    OCPUs: {vm.shape_config.ocpus}")
                speak_plain(f"    Memory: {vm.shape_config.memory_in_gbs} GB")

            speak_plain("")

            if vm.lifecycle_state == "RUNNING":
                running += 1
            elif vm.lifecycle_state == "STOPPED":
                stopped += 1

        speak_plain(f"Total: {len(instances)} VMs ({running} running, {stopped} stopped)")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_vm(args):
    """Show detailed VM information."""
    speak(f"Fetching details for instance {args.instance_id}...")

    config = get_oci_config(args.profile)
    compute, _, network = get_clients(config)

    try:
        vm = compute.get_instance(args.instance_id).data

        speak_plain("")
        speak_plain("Virtual Machine Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {vm.display_name}")
        speak_plain(f"  Instance ID: {vm.id}")
        speak_plain(f"  State: {format_state(vm.lifecycle_state)}")
        speak_plain(f"  Availability Domain: {vm.availability_domain}")
        speak_plain(f"  Fault Domain: {vm.fault_domain}")
        speak_plain(f"  Shape: {vm.shape}")

        if vm.shape_config:
            speak_plain(f"  OCPUs: {vm.shape_config.ocpus}")
            speak_plain(f"  Memory: {vm.shape_config.memory_in_gbs} GB")
            if vm.shape_config.gpus:
                speak_plain(f"  GPUs: {vm.shape_config.gpus}")

        speak_plain(f"  Created: {vm.time_created.strftime('%Y-%m-%d %H:%M:%S')}")
        speak_plain(f"  Region: {vm.region}")
        speak_plain(f"  Compartment ID: {vm.compartment_id}")

        # Get VNIC attachments for IP addresses
        speak_plain("")
        speak_plain("  Network:")

        vnics = compute.list_vnic_attachments(
            compartment_id=vm.compartment_id,
            instance_id=vm.id
        ).data

        for vnic_att in vnics:
            if vnic_att.lifecycle_state == "ATTACHED":
                vnic = network.get_vnic(vnic_att.vnic_id).data
                speak_plain(f"    Private IP: {vnic.private_ip}")
                if vnic.public_ip:
                    speak_plain(f"    Public IP: {vnic.public_ip}")
                speak_plain(f"    MAC Address: {vnic.mac_address}")

        # Boot volume
        speak_plain("")
        speak_plain("  Boot Volume:")
        boot_vols = compute.list_boot_volume_attachments(
            availability_domain=vm.availability_domain,
            compartment_id=vm.compartment_id,
            instance_id=vm.id
        ).data

        for bv in boot_vols:
            speak_plain(f"    Boot Volume ID: {bv.boot_volume_id}")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def start_vm(args):
    """Start a stopped VM."""
    speak(f"Starting instance {args.instance_id}...")

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)

    try:
        compute.instance_action(args.instance_id, "START")
        speak("Start command sent successfully.")

        if args.wait:
            speak("Waiting for instance to start...")
            oci.wait_until(
                compute,
                compute.get_instance(args.instance_id),
                "lifecycle_state",
                "RUNNING",
                max_wait_seconds=300
            )
            speak("Instance is now running.")
        else:
            speak("Instance is starting. Use 'orcvm.py show' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def stop_vm(args):
    """Stop a running VM."""
    speak(f"Stopping instance {args.instance_id}...")

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)

    try:
        action = "SOFTSTOP" if not args.force else "STOP"
        compute.instance_action(args.instance_id, action)
        speak(f"{'Force stop' if args.force else 'Stop'} command sent successfully.")

        if args.wait:
            speak("Waiting for instance to stop...")
            oci.wait_until(
                compute,
                compute.get_instance(args.instance_id),
                "lifecycle_state",
                "STOPPED",
                max_wait_seconds=300
            )
            speak("Instance has stopped.")
        else:
            speak("Instance is stopping. Use 'orcvm.py show' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def reboot_vm(args):
    """Reboot a VM."""
    speak(f"Rebooting instance {args.instance_id}...")

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)

    try:
        action = "SOFTRESET" if not args.force else "RESET"
        compute.instance_action(args.instance_id, action)
        speak(f"{'Force reboot' if args.force else 'Reboot'} command sent successfully.")

        if args.wait:
            speak("Waiting for instance to reboot...")
            time.sleep(10)  # Brief pause before checking
            oci.wait_until(
                compute,
                compute.get_instance(args.instance_id),
                "lifecycle_state",
                "RUNNING",
                max_wait_seconds=300
            )
            speak("Instance has rebooted and is running.")
        else:
            speak("Instance is rebooting. Use 'orcvm.py show' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def terminate_vm(args):
    """Terminate a VM permanently."""
    speak(f"WARNING: Terminating instance {args.instance_id}")
    speak("This action is PERMANENT and cannot be undone!")

    if not args.yes:
        confirm = input("Type 'yes' to confirm termination: ")
        if confirm.lower() != "yes":
            speak("Termination cancelled.")
            return

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)

    try:
        compute.terminate_instance(
            args.instance_id,
            preserve_boot_volume=args.preserve_boot_volume
        )
        speak("Termination command sent.")

        if args.preserve_boot_volume:
            speak("Boot volume will be preserved.")
        else:
            speak("Boot volume will be deleted.")

        if args.wait:
            speak("Waiting for termination...")
            oci.wait_until(
                compute,
                compute.get_instance(args.instance_id),
                "lifecycle_state",
                "TERMINATED",
                max_wait_seconds=300
            )
            speak("Instance has been terminated.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_images(args):
    """List available OS images."""
    speak("Fetching available images...")

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        # Get images, optionally filtered by OS and shape
        kwargs = {
            "compartment_id": compartment_id,
            "sort_by": "TIMECREATED",
            "sort_order": "DESC",
            "limit": args.limit
        }

        if args.os:
            kwargs["operating_system"] = args.os
        if args.shape:
            kwargs["shape"] = args.shape

        response = compute.list_images(**kwargs)
        images = response.data

        if not images:
            speak_plain("")
            speak_plain("No images found matching criteria.")
            return

        speak_plain("")
        speak_plain("Available OS Images")
        speak_plain("=" * 70)
        speak_plain("")

        current_os = None
        for img in images:
            if args.os is None and img.operating_system != current_os:
                current_os = img.operating_system
                speak_plain(f"--- {current_os} ---")
                speak_plain("")

            speak_plain(f"  {img.display_name}")
            speak_plain(f"    ID: {img.id}")
            speak_plain(f"    OS: {img.operating_system} {img.operating_system_version}")
            speak_plain(f"    Created: {img.time_created.strftime('%Y-%m-%d')}")
            speak_plain("")

        speak_plain(f"Total: {len(images)} images")
        speak_plain("")
        speak_plain("Tip: Use --os 'Canonical Ubuntu' or --shape VM.Standard.A1.Flex to filter")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_shapes(args):
    """List available VM shapes."""
    speak("Fetching available shapes...")

    config = get_oci_config(args.profile)
    compute, _, _ = get_clients(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = compute.list_shapes(compartment_id=compartment_id)
        shapes = response.data

        speak_plain("")
        speak_plain("Available VM Shapes")
        speak_plain("=" * 70)
        speak_plain("")

        # Group by type
        flex_shapes = []
        fixed_shapes = []

        for shape in shapes:
            if ".Flex" in shape.shape:
                flex_shapes.append(shape)
            else:
                fixed_shapes.append(shape)

        if flex_shapes:
            speak_plain("--- Flexible Shapes (recommended) ---")
            speak_plain("")
            for shape in flex_shapes:
                speak_plain(f"  {shape.shape}")
                speak_plain(f"    OCPUs: {shape.ocpu_options.min} to {shape.ocpu_options.max}")
                speak_plain(f"    Memory per OCPU: {shape.memory_options.min_per_ocpu_in_gbs} to {shape.memory_options.max_per_ocpu_in_gbs} GB")
                if shape.is_flexible:
                    speak_plain("    Type: Flexible (choose OCPUs and memory)")
                speak_plain("")

        if fixed_shapes and not args.flex_only:
            speak_plain("--- Fixed Shapes ---")
            speak_plain("")
            for shape in fixed_shapes[:20]:  # Limit output
                speak_plain(f"  {shape.shape}")
                speak_plain(f"    OCPUs: {shape.ocpus}")
                speak_plain(f"    Memory: {shape.memory_in_gbs} GB")
                speak_plain("")

            if len(fixed_shapes) > 20:
                speak_plain(f"  ... and {len(fixed_shapes) - 20} more fixed shapes")

        speak_plain("")
        speak_plain(f"Total: {len(shapes)} shapes available")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def export_config(args):
    """Export a VM configuration template."""
    template = {
        "_comment": "VM Configuration Template",
        "_instructions": [
            "1. Get compartment_id: orcvm.py list-compartments",
            "2. Get subnet_id: orcvm.py list-subnets",
            "3. Get image_id: orcvm.py images --os 'Canonical Ubuntu'",
            "4. Add your SSH public key",
            "5. Run: orcvm.py create --config this-file.json"
        ],
        "display_name": "my-vm",
        "compartment_id": "ocid1.compartment.oc1..your-compartment-id",
        "availability_domain": "AD-1",
        "shape": "VM.Standard.A1.Flex",
        "shape_config": {
            "ocpus": 1,
            "memory_in_gbs": 6
        },
        "source_details": {
            "source_type": "image",
            "image_id": "ocid1.image.oc1..your-image-id",
            "boot_volume_size_in_gbs": 50
        },
        "create_vnic_details": {
            "subnet_id": "ocid1.subnet.oc1..your-subnet-id",
            "assign_public_ip": True
        },
        "metadata": {
            "ssh_authorized_keys": "ssh-rsa AAAA... your-public-key"
        },
        "freeform_tags": {
            "Environment": "development",
            "ManagedBy": "orcvm"
        }
    }

    output_path = Path(args.output).expanduser()
    with open(output_path, "w") as f:
        json.dump(template, f, indent=2)

    speak_plain(f"Configuration template saved to: {args.output}")
    speak_plain("")
    speak_plain("Next steps:")
    speak_plain("  1. Edit the file with your settings")
    speak_plain("  2. Run: orcvm.py create --config " + args.output)


def create_vm(args):
    """Create a new VM from configuration."""
    speak("Loading configuration...")

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    with open(config_path) as f:
        vm_config = json.load(f)

    # Validate required fields
    required = ["display_name", "compartment_id", "shape"]
    for field in required:
        if field not in vm_config:
            print(f"Error: Required field '{field}' missing from config")
            sys.exit(1)

    speak(f"Creating VM: {vm_config['display_name']}")

    oci_config = get_oci_config(args.profile)
    compute, identity, _ = get_clients(oci_config)

    try:
        # Get availability domain if not specified
        ad = vm_config.get("availability_domain")
        if ad and not ad.startswith("ocid"):
            # Convert AD-1, AD-2, AD-3 to full name
            ads = identity.list_availability_domains(vm_config["compartment_id"]).data
            if ad.upper().startswith("AD-"):
                ad_num = int(ad.split("-")[1]) - 1
                if ad_num < len(ads):
                    ad = ads[ad_num].name
                else:
                    ad = ads[0].name
            else:
                ad = ads[0].name
        elif not ad:
            ads = identity.list_availability_domains(vm_config["compartment_id"]).data
            ad = ads[0].name

        # Build launch details
        shape_config = None
        if "shape_config" in vm_config:
            shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=float(vm_config["shape_config"].get("ocpus", 1)),
                memory_in_gbs=float(vm_config["shape_config"].get("memory_in_gbs", 6))
            )

        source_details = None
        if "source_details" in vm_config:
            sd = vm_config["source_details"]
            source_details = oci.core.models.InstanceSourceViaImageDetails(
                image_id=sd["image_id"],
                boot_volume_size_in_gbs=sd.get("boot_volume_size_in_gbs", 50)
            )

        vnic_details = None
        if "create_vnic_details" in vm_config:
            vd = vm_config["create_vnic_details"]
            vnic_details = oci.core.models.CreateVnicDetails(
                subnet_id=vd["subnet_id"],
                assign_public_ip=vd.get("assign_public_ip", True)
            )

        launch_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=ad,
            compartment_id=vm_config["compartment_id"],
            display_name=vm_config["display_name"],
            shape=vm_config["shape"],
            shape_config=shape_config,
            source_details=source_details,
            create_vnic_details=vnic_details,
            metadata=vm_config.get("metadata", {}),
            freeform_tags=vm_config.get("freeform_tags", {})
        )

        response = compute.launch_instance(launch_details)
        instance = response.data

        speak("VM creation initiated!")
        speak_plain("")
        speak_plain(f"  Instance ID: {instance.id}")
        speak_plain(f"  Name: {instance.display_name}")
        speak_plain(f"  State: {format_state(instance.lifecycle_state)}")

        if args.wait:
            speak("Waiting for VM to be ready...")
            instance = oci.wait_until(
                compute,
                compute.get_instance(instance.id),
                "lifecycle_state",
                "RUNNING",
                max_wait_seconds=600
            ).data
            speak("VM is now running!")
            speak("Use 'orcvm.py show " + instance.id + "' to see IP address")
        else:
            speak("VM is provisioning. Use 'orcvm.py show' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_subnets(args):
    """List available subnets."""
    speak("Fetching subnets...")

    config = get_oci_config(args.profile)
    _, _, network = get_clients(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = network.list_subnets(compartment_id=compartment_id)
        subnets = response.data

        if not subnets:
            speak_plain("")
            speak_plain("No subnets found.")
            speak_plain("Create a VCN and subnet in the Oracle Cloud Console first.")
            return

        speak_plain("")
        speak_plain("Available Subnets")
        speak_plain("=" * 70)
        speak_plain("")

        for subnet in subnets:
            speak_plain(f"  Name: {subnet.display_name}")
            speak_plain(f"    ID: {subnet.id}")
            speak_plain(f"    CIDR: {subnet.cidr_block}")
            speak_plain(f"    VCN ID: {subnet.vcn_id}")
            speak_plain(f"    Public: {'Yes' if subnet.prohibit_public_ip_on_vnic == False else 'No'}")
            speak_plain("")

        speak_plain(f"Total: {len(subnets)} subnets")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_compartments(args):
    """List available compartments."""
    speak("Fetching compartments...")

    config = get_oci_config(args.profile)
    _, identity, _ = get_clients(config)
    tenancy_id = config["tenancy"]

    try:
        response = identity.list_compartments(
            compartment_id=tenancy_id,
            compartment_id_in_subtree=True,
            lifecycle_state="ACTIVE"
        )

        speak_plain("")
        speak_plain("Available Compartments")
        speak_plain("=" * 70)
        speak_plain("")

        # Root compartment
        speak_plain(f"  Name: root (tenancy)")
        speak_plain(f"    ID: {tenancy_id}")
        speak_plain("")

        for comp in response.data:
            speak_plain(f"  Name: {comp.name}")
            speak_plain(f"    ID: {comp.id}")
            if comp.description:
                speak_plain(f"    Description: {comp.description}")
            speak_plain("")

        speak_plain(f"Total: {len(response.data) + 1} compartments")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Cloud VM Management Tool. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    orcvm.py list                          # List all VMs
    orcvm.py show ocid1.instance...        # Show VM details
    orcvm.py start ocid1.instance...       # Start VM
    orcvm.py stop ocid1.instance...        # Stop VM
    orcvm.py reboot ocid1.instance...      # Reboot VM
    orcvm.py terminate ocid1.instance...   # Delete VM

    orcvm.py images --os "Canonical Ubuntu"  # List Ubuntu images
    orcvm.py shapes --flex-only              # List flex shapes

    orcvm.py export-config my-vm.json      # Create config template
    orcvm.py create --config my-vm.json    # Create VM from config

Screen Reader Notes:
    All output is plain text with clear labels.
    Lists use consistent indentation.
    Status messages include timestamps.
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

    # list
    list_parser = subparsers.add_parser("list", help="List all VMs")
    list_parser.set_defaults(func=list_vms)

    # show
    show_parser = subparsers.add_parser("show", help="Show VM details")
    show_parser.add_argument("instance_id", help="Instance OCID")
    show_parser.set_defaults(func=show_vm)

    # start
    start_parser = subparsers.add_parser("start", help="Start a stopped VM")
    start_parser.add_argument("instance_id", help="Instance OCID")
    start_parser.add_argument("--wait", "-w", action="store_true", help="Wait for VM to start")
    start_parser.set_defaults(func=start_vm)

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop a running VM")
    stop_parser.add_argument("instance_id", help="Instance OCID")
    stop_parser.add_argument("--force", "-f", action="store_true", help="Force stop (power off)")
    stop_parser.add_argument("--wait", "-w", action="store_true", help="Wait for VM to stop")
    stop_parser.set_defaults(func=stop_vm)

    # reboot
    reboot_parser = subparsers.add_parser("reboot", help="Reboot a VM")
    reboot_parser.add_argument("instance_id", help="Instance OCID")
    reboot_parser.add_argument("--force", "-f", action="store_true", help="Force reboot (hard reset)")
    reboot_parser.add_argument("--wait", "-w", action="store_true", help="Wait for reboot")
    reboot_parser.set_defaults(func=reboot_vm)

    # terminate
    term_parser = subparsers.add_parser("terminate", help="Terminate VM permanently")
    term_parser.add_argument("instance_id", help="Instance OCID")
    term_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    term_parser.add_argument("--preserve-boot-volume", action="store_true", help="Keep boot volume")
    term_parser.add_argument("--wait", "-w", action="store_true", help="Wait for termination")
    term_parser.set_defaults(func=terminate_vm)

    # images
    img_parser = subparsers.add_parser("images", help="List available OS images")
    img_parser.add_argument("--os", help="Filter by OS (e.g., 'Canonical Ubuntu')")
    img_parser.add_argument("--shape", help="Filter by compatible shape")
    img_parser.add_argument("--limit", type=int, default=50, help="Max images to show")
    img_parser.set_defaults(func=list_images)

    # shapes
    shape_parser = subparsers.add_parser("shapes", help="List available VM shapes")
    shape_parser.add_argument("--flex-only", action="store_true", help="Show only flexible shapes")
    shape_parser.set_defaults(func=list_shapes)

    # create
    create_parser = subparsers.add_parser("create", help="Create VM from config")
    create_parser.add_argument("--config", required=True, help="Config file path")
    create_parser.add_argument("--wait", "-w", action="store_true", help="Wait for VM to be ready")
    create_parser.set_defaults(func=create_vm)

    # export-config
    export_parser = subparsers.add_parser("export-config", help="Export config template")
    export_parser.add_argument("output", help="Output file path")
    export_parser.set_defaults(func=export_config)

    # list-subnets
    subnet_parser = subparsers.add_parser("list-subnets", help="List available subnets")
    subnet_parser.set_defaults(func=list_subnets)

    # list-compartments
    comp_parser = subparsers.add_parser("list-compartments", help="List compartments")
    comp_parser.set_defaults(func=list_compartments)

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
