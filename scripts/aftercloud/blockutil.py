#!/usr/bin/env python3
"""
Oracle Cloud Block Storage Utility

Manage Oracle Cloud Infrastructure block volumes and boot volumes.
Designed for accessibility with screen reader friendly output.

Usage:
    blockutil.py list                      # List all block volumes
    blockutil.py list-boot                 # List boot volumes
    blockutil.py show <volume-id>          # Show volume details
    blockutil.py create --config vol.json  # Create block volume
    blockutil.py attach <vol-id> <inst-id> # Attach to instance
    blockutil.py detach <attachment-id>    # Detach from instance
    blockutil.py resize <volume-id> <size> # Resize volume
    blockutil.py delete <volume-id>        # Delete volume
    blockutil.py backup <volume-id>        # Create backup
    blockutil.py backups                   # List backups
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
    """Print without timestamp."""
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


def format_size(size_gb: int) -> str:
    """Format size for display."""
    if size_gb >= 1024:
        return f"{size_gb / 1024:.1f} TB"
    return f"{size_gb} GB"


def format_state(state: str) -> str:
    """Format lifecycle state for readability."""
    states = {
        "AVAILABLE": "Available",
        "PROVISIONING": "Provisioning",
        "TERMINATING": "Terminating",
        "TERMINATED": "Terminated",
        "RESTORING": "Restoring",
        "FAULTY": "Faulty",
    }
    return states.get(state, state)


def list_volumes(args):
    """List all block volumes."""
    speak("Fetching block volumes...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = blockstorage.list_volumes(compartment_id=compartment_id)
        volumes = response.data

        if not volumes:
            speak_plain("")
            speak_plain("No block volumes found.")
            speak_plain("Use 'blockutil.py create --config vol.json' to create one.")
            return

        speak_plain("")
        speak_plain("Block Volumes")
        speak_plain("=" * 70)
        speak_plain("")

        total_size = 0
        available = 0

        for vol in volumes:
            if vol.lifecycle_state == "TERMINATED":
                continue

            speak_plain(f"  Name: {vol.display_name}")
            speak_plain(f"    ID: {vol.id}")
            speak_plain(f"    State: {format_state(vol.lifecycle_state)}")
            speak_plain(f"    Size: {format_size(vol.size_in_gbs)}")
            speak_plain(f"    Performance: {vol.vpus_per_gb} VPUs/GB")
            speak_plain(f"    Availability Domain: {vol.availability_domain}")
            speak_plain(f"    Created: {vol.time_created.strftime('%Y-%m-%d %H:%M')}")
            speak_plain("")

            total_size += vol.size_in_gbs
            if vol.lifecycle_state == "AVAILABLE":
                available += 1

        active_count = len([v for v in volumes if v.lifecycle_state != "TERMINATED"])
        speak_plain(f"Total: {active_count} volumes, {format_size(total_size)} total storage")
        speak_plain(f"Available: {available} volumes")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_boot_volumes(args):
    """List all boot volumes."""
    speak("Fetching boot volumes...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)
    identity = oci.identity.IdentityClient(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        # Get availability domains
        ads = identity.list_availability_domains(compartment_id).data

        all_boot_volumes = []
        for ad in ads:
            response = blockstorage.list_boot_volumes(
                availability_domain=ad.name,
                compartment_id=compartment_id
            )
            all_boot_volumes.extend(response.data)

        if not all_boot_volumes:
            speak_plain("")
            speak_plain("No boot volumes found.")
            return

        speak_plain("")
        speak_plain("Boot Volumes")
        speak_plain("=" * 70)
        speak_plain("")

        total_size = 0

        for vol in all_boot_volumes:
            if vol.lifecycle_state == "TERMINATED":
                continue

            speak_plain(f"  Name: {vol.display_name}")
            speak_plain(f"    ID: {vol.id}")
            speak_plain(f"    State: {format_state(vol.lifecycle_state)}")
            speak_plain(f"    Size: {format_size(vol.size_in_gbs)}")
            speak_plain(f"    Image ID: {vol.image_id}")
            speak_plain(f"    Availability Domain: {vol.availability_domain}")
            speak_plain("")

            total_size += vol.size_in_gbs

        active_count = len([v for v in all_boot_volumes if v.lifecycle_state != "TERMINATED"])
        speak_plain(f"Total: {active_count} boot volumes, {format_size(total_size)} total storage")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_volume(args):
    """Show detailed volume information."""
    speak(f"Fetching volume {args.volume_id}...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)
    compute = oci.core.ComputeClient(config)

    try:
        volume = blockstorage.get_volume(args.volume_id).data

        speak_plain("")
        speak_plain("Block Volume Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {volume.display_name}")
        speak_plain(f"  ID: {volume.id}")
        speak_plain(f"  State: {format_state(volume.lifecycle_state)}")
        speak_plain(f"  Size: {format_size(volume.size_in_gbs)}")
        speak_plain(f"  Performance: {volume.vpus_per_gb} VPUs/GB")
        speak_plain(f"  Availability Domain: {volume.availability_domain}")
        speak_plain(f"  Compartment ID: {volume.compartment_id}")
        speak_plain(f"  Created: {volume.time_created.strftime('%Y-%m-%d %H:%M:%S')}")

        if volume.is_auto_tune_enabled:
            speak_plain("  Auto-Tune: Enabled")

        # Check for attachments
        speak_plain("")
        speak_plain("  Attachments:")

        attachments = compute.list_volume_attachments(
            compartment_id=volume.compartment_id,
            volume_id=volume.id
        ).data

        attached = [a for a in attachments if a.lifecycle_state == "ATTACHED"]
        if attached:
            for att in attached:
                speak_plain(f"    Instance ID: {att.instance_id}")
                speak_plain(f"      Device: {att.device}")
                speak_plain(f"      Attachment Type: {att.attachment_type}")
                speak_plain(f"      Read-Only: {'Yes' if att.is_read_only else 'No'}")
        else:
            speak_plain("    Not attached to any instance")

        # Tags
        if volume.freeform_tags:
            speak_plain("")
            speak_plain("  Tags:")
            for key, value in volume.freeform_tags.items():
                speak_plain(f"    {key}: {value}")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def create_volume(args):
    """Create a new block volume."""
    speak("Loading configuration...")

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    with open(config_path) as f:
        vol_config = json.load(f)

    # Validate required fields
    required = ["display_name", "compartment_id", "availability_domain", "size_in_gbs"]
    for field in required:
        if field not in vol_config:
            print(f"Error: Required field '{field}' missing from config")
            sys.exit(1)

    speak(f"Creating volume: {vol_config['display_name']}")

    oci_config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(oci_config)
    identity = oci.identity.IdentityClient(oci_config)

    try:
        # Get availability domain
        ad = vol_config["availability_domain"]
        if not ad.startswith("ocid") and not ":" in ad:
            ads = identity.list_availability_domains(vol_config["compartment_id"]).data
            if ad.upper().startswith("AD-"):
                ad_num = int(ad.split("-")[1]) - 1
                if ad_num < len(ads):
                    ad = ads[ad_num].name
                else:
                    ad = ads[0].name
            else:
                ad = ads[0].name

        create_details = oci.core.models.CreateVolumeDetails(
            compartment_id=vol_config["compartment_id"],
            availability_domain=ad,
            display_name=vol_config["display_name"],
            size_in_gbs=vol_config["size_in_gbs"],
            vpus_per_gb=vol_config.get("vpus_per_gb", 10),
            is_auto_tune_enabled=vol_config.get("is_auto_tune_enabled", False),
            freeform_tags=vol_config.get("freeform_tags", {})
        )

        response = blockstorage.create_volume(create_details)
        volume = response.data

        speak("Volume creation initiated!")
        speak_plain("")
        speak_plain(f"  Volume ID: {volume.id}")
        speak_plain(f"  Name: {volume.display_name}")
        speak_plain(f"  State: {format_state(volume.lifecycle_state)}")
        speak_plain(f"  Size: {format_size(volume.size_in_gbs)}")

        if args.wait:
            speak("Waiting for volume to be available...")
            volume = oci.wait_until(
                blockstorage,
                blockstorage.get_volume(volume.id),
                "lifecycle_state",
                "AVAILABLE",
                max_wait_seconds=300
            ).data
            speak("Volume is now available!")
        else:
            speak("Volume is being created. Use 'blockutil.py show' to check status.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def attach_volume(args):
    """Attach volume to instance."""
    speak(f"Attaching volume {args.volume_id} to instance {args.instance_id}...")

    config = get_oci_config(args.profile)
    compute = oci.core.ComputeClient(config)

    try:
        # Determine attachment type
        attachment_type = args.type or "paravirtualized"

        if attachment_type == "iscsi":
            attach_details = oci.core.models.AttachIScsiVolumeDetails(
                instance_id=args.instance_id,
                volume_id=args.volume_id,
                display_name=args.name or "attached-volume",
                is_read_only=args.read_only,
                is_shareable=args.shareable
            )
        else:
            attach_details = oci.core.models.AttachParavirtualizedVolumeDetails(
                instance_id=args.instance_id,
                volume_id=args.volume_id,
                display_name=args.name or "attached-volume",
                is_read_only=args.read_only,
                is_shareable=args.shareable
            )

        response = compute.attach_volume(attach_details)
        attachment = response.data

        speak("Volume attachment initiated!")
        speak_plain("")
        speak_plain(f"  Attachment ID: {attachment.id}")
        speak_plain(f"  Attachment Type: {attachment.attachment_type}")
        speak_plain(f"  State: {attachment.lifecycle_state}")

        if args.wait:
            speak("Waiting for attachment to complete...")
            attachment = oci.wait_until(
                compute,
                compute.get_volume_attachment(attachment.id),
                "lifecycle_state",
                "ATTACHED",
                max_wait_seconds=300
            ).data
            speak("Volume attached successfully!")
            speak_plain(f"  Device: {attachment.device}")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def detach_volume(args):
    """Detach volume from instance."""
    speak(f"Detaching volume attachment {args.attachment_id}...")

    config = get_oci_config(args.profile)
    compute = oci.core.ComputeClient(config)

    try:
        compute.detach_volume(args.attachment_id)
        speak("Detachment initiated.")

        if args.wait:
            speak("Waiting for detachment to complete...")
            oci.wait_until(
                compute,
                compute.get_volume_attachment(args.attachment_id),
                "lifecycle_state",
                "DETACHED",
                max_wait_seconds=300
            )
            speak("Volume detached successfully!")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def resize_volume(args):
    """Resize a block volume."""
    speak(f"Resizing volume {args.volume_id} to {args.size_gb} GB...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)

    try:
        # Get current volume
        current = blockstorage.get_volume(args.volume_id).data

        if args.size_gb <= current.size_in_gbs:
            print(f"Error: New size ({args.size_gb} GB) must be larger than current size ({current.size_in_gbs} GB)")
            print("Oracle Cloud does not support shrinking volumes.")
            sys.exit(1)

        speak(f"Current size: {format_size(current.size_in_gbs)}")
        speak(f"New size: {format_size(args.size_gb)}")

        update_details = oci.core.models.UpdateVolumeDetails(
            size_in_gbs=args.size_gb
        )

        response = blockstorage.update_volume(args.volume_id, update_details)
        volume = response.data

        speak("Resize initiated!")

        if args.wait:
            speak("Waiting for resize to complete...")
            volume = oci.wait_until(
                blockstorage,
                blockstorage.get_volume(args.volume_id),
                "lifecycle_state",
                "AVAILABLE",
                max_wait_seconds=600
            ).data
            speak(f"Volume resized to {format_size(volume.size_in_gbs)}")
            speak_plain("")
            speak_plain("Note: You may need to extend the filesystem inside the OS.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def delete_volume(args):
    """Delete a block volume."""
    speak(f"WARNING: Deleting volume {args.volume_id}")
    speak("This action is PERMANENT and cannot be undone!")

    if not args.yes:
        confirm = input("Type 'yes' to confirm deletion: ")
        if confirm.lower() != "yes":
            speak("Deletion cancelled.")
            return

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)

    try:
        blockstorage.delete_volume(args.volume_id)
        speak("Volume deletion initiated.")

        if args.wait:
            speak("Waiting for deletion to complete...")
            oci.wait_until(
                blockstorage,
                blockstorage.get_volume(args.volume_id),
                "lifecycle_state",
                "TERMINATED",
                max_wait_seconds=300,
                succeed_on_not_found=True
            )
            speak("Volume has been deleted.")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def create_backup(args):
    """Create a volume backup."""
    speak(f"Creating backup of volume {args.volume_id}...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)

    try:
        # Get volume details for naming
        volume = blockstorage.get_volume(args.volume_id).data
        backup_name = args.name or f"{volume.display_name}-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        backup_details = oci.core.models.CreateVolumeBackupDetails(
            volume_id=args.volume_id,
            display_name=backup_name,
            type=args.backup_type or "INCREMENTAL",
            freeform_tags=volume.freeform_tags or {}
        )

        response = blockstorage.create_volume_backup(backup_details)
        backup = response.data

        speak("Backup creation initiated!")
        speak_plain("")
        speak_plain(f"  Backup ID: {backup.id}")
        speak_plain(f"  Name: {backup.display_name}")
        speak_plain(f"  Type: {backup.type}")
        speak_plain(f"  State: {backup.lifecycle_state}")

        if args.wait:
            speak("Waiting for backup to complete...")
            speak("This may take several minutes depending on volume size.")
            backup = oci.wait_until(
                blockstorage,
                blockstorage.get_volume_backup(backup.id),
                "lifecycle_state",
                "AVAILABLE",
                max_wait_seconds=3600
            ).data
            speak(f"Backup complete! Size: {format_size(backup.size_in_gbs)}")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_backups(args):
    """List all volume backups."""
    speak("Fetching volume backups...")

    config = get_oci_config(args.profile)
    blockstorage = oci.core.BlockstorageClient(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        response = blockstorage.list_volume_backups(compartment_id=compartment_id)
        backups = response.data

        if not backups:
            speak_plain("")
            speak_plain("No volume backups found.")
            speak_plain("Use 'blockutil.py backup <volume-id>' to create one.")
            return

        speak_plain("")
        speak_plain("Volume Backups")
        speak_plain("=" * 70)
        speak_plain("")

        total_size = 0

        for backup in backups:
            if backup.lifecycle_state == "TERMINATED":
                continue

            speak_plain(f"  Name: {backup.display_name}")
            speak_plain(f"    ID: {backup.id}")
            speak_plain(f"    State: {format_state(backup.lifecycle_state)}")
            speak_plain(f"    Size: {format_size(backup.size_in_gbs) if backup.size_in_gbs else 'N/A'}")
            speak_plain(f"    Type: {backup.type}")
            speak_plain(f"    Source Volume: {backup.volume_id}")
            speak_plain(f"    Created: {backup.time_created.strftime('%Y-%m-%d %H:%M')}")
            speak_plain("")

            if backup.size_in_gbs:
                total_size += backup.size_in_gbs

        active_count = len([b for b in backups if b.lifecycle_state != "TERMINATED"])
        speak_plain(f"Total: {active_count} backups, {format_size(total_size)} total storage")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def export_config(args):
    """Export volume configuration template."""
    template = {
        "_comment": "Block Volume Configuration Template",
        "_instructions": [
            "1. Get compartment_id: blockutil.py list-compartments",
            "2. Choose availability_domain (AD-1, AD-2, or AD-3)",
            "3. Set size_in_gbs (minimum 50 GB)",
            "4. Set vpus_per_gb for performance (0=lower cost, 10=balanced, 20=high)",
            "5. Run: blockutil.py create --config this-file.json"
        ],
        "display_name": "my-block-volume",
        "compartment_id": "ocid1.compartment.oc1..your-compartment-id",
        "availability_domain": "AD-1",
        "size_in_gbs": 100,
        "vpus_per_gb": 10,
        "is_auto_tune_enabled": False,
        "freeform_tags": {
            "Environment": "development",
            "ManagedBy": "blockutil"
        }
    }

    output_path = Path(args.output).expanduser()
    with open(output_path, "w") as f:
        json.dump(template, f, indent=2)

    speak_plain(f"Configuration template saved to: {args.output}")
    speak_plain("")
    speak_plain("Performance tiers (vpus_per_gb):")
    speak_plain("  0  - Lower Cost (2 VPUs per GB)")
    speak_plain("  10 - Balanced (10 VPUs per GB)")
    speak_plain("  20 - Higher Performance (20 VPUs per GB)")


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Cloud Block Storage Utility. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    blockutil.py list                          # List block volumes
    blockutil.py list-boot                     # List boot volumes
    blockutil.py show ocid1.volume...          # Show volume details
    blockutil.py create --config vol.json      # Create volume
    blockutil.py attach <vol-id> <inst-id>     # Attach to instance
    blockutil.py detach <attachment-id>        # Detach from instance
    blockutil.py resize <vol-id> 200           # Resize to 200 GB
    blockutil.py delete <vol-id>               # Delete volume
    blockutil.py backup <vol-id>               # Create backup
    blockutil.py backups                       # List backups

Screen Reader Notes:
    All output is plain text with clear labels.
    Sizes are formatted (e.g., "1.5 TB" instead of "1536 GB").
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
    list_parser = subparsers.add_parser("list", help="List block volumes")
    list_parser.set_defaults(func=list_volumes)

    # list-boot
    list_boot_parser = subparsers.add_parser("list-boot", help="List boot volumes")
    list_boot_parser.set_defaults(func=list_boot_volumes)

    # show
    show_parser = subparsers.add_parser("show", help="Show volume details")
    show_parser.add_argument("volume_id", help="Volume OCID")
    show_parser.set_defaults(func=show_volume)

    # create
    create_parser = subparsers.add_parser("create", help="Create block volume")
    create_parser.add_argument("--config", required=True, help="Config file path")
    create_parser.add_argument("--wait", "-w", action="store_true", help="Wait for available")
    create_parser.set_defaults(func=create_volume)

    # attach
    attach_parser = subparsers.add_parser("attach", help="Attach volume to instance")
    attach_parser.add_argument("volume_id", help="Volume OCID")
    attach_parser.add_argument("instance_id", help="Instance OCID")
    attach_parser.add_argument("--name", help="Attachment display name")
    attach_parser.add_argument("--type", choices=["paravirtualized", "iscsi"], help="Attachment type")
    attach_parser.add_argument("--read-only", action="store_true", help="Mount read-only")
    attach_parser.add_argument("--shareable", action="store_true", help="Allow multi-attach")
    attach_parser.add_argument("--wait", "-w", action="store_true", help="Wait for attach")
    attach_parser.set_defaults(func=attach_volume)

    # detach
    detach_parser = subparsers.add_parser("detach", help="Detach volume from instance")
    detach_parser.add_argument("attachment_id", help="Attachment OCID")
    detach_parser.add_argument("--wait", "-w", action="store_true", help="Wait for detach")
    detach_parser.set_defaults(func=detach_volume)

    # resize
    resize_parser = subparsers.add_parser("resize", help="Resize block volume")
    resize_parser.add_argument("volume_id", help="Volume OCID")
    resize_parser.add_argument("size_gb", type=int, help="New size in GB")
    resize_parser.add_argument("--wait", "-w", action="store_true", help="Wait for resize")
    resize_parser.set_defaults(func=resize_volume)

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete block volume")
    delete_parser.add_argument("volume_id", help="Volume OCID")
    delete_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    delete_parser.add_argument("--wait", "-w", action="store_true", help="Wait for deletion")
    delete_parser.set_defaults(func=delete_volume)

    # backup
    backup_parser = subparsers.add_parser("backup", help="Create volume backup")
    backup_parser.add_argument("volume_id", help="Volume OCID")
    backup_parser.add_argument("--name", help="Backup display name")
    backup_parser.add_argument("--backup-type", choices=["FULL", "INCREMENTAL"], default="INCREMENTAL")
    backup_parser.add_argument("--wait", "-w", action="store_true", help="Wait for backup")
    backup_parser.set_defaults(func=create_backup)

    # backups
    backups_parser = subparsers.add_parser("backups", help="List volume backups")
    backups_parser.set_defaults(func=list_backups)

    # export-config
    export_parser = subparsers.add_parser("export-config", help="Export config template")
    export_parser.add_argument("output", help="Output file path")
    export_parser.set_defaults(func=export_config)

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
