#!/usr/bin/env python3
"""
OCI Free Tier Instance Retry Script

Repeatedly attempts to launch an Oracle Cloud free tier instance until successful.
Designed for accessibility - uses clear text output compatible with screen readers.

Usage:
    python3 oci_free_instance.py --config config.json
    python3 oci_free_instance.py --regions                    # List all regions
    python3 oci_free_instance.py --shapes                     # List free tier shapes
    python3 oci_free_instance.py --compartments               # List compartments
    python3 oci_free_instance.py --export-config config.json  # Generate config template
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Check for required library
try:
    import oci
except ImportError:
    print("Error: OCI Python SDK not installed.")
    print("Install it with: pip install oci")
    print("Or: pip3 install oci")
    sys.exit(1)


# Oracle Cloud regions with free tier availability
OCI_REGIONS = [
    {"name": "us-ashburn-1", "location": "Ashburn, Virginia, USA"},
    {"name": "us-phoenix-1", "location": "Phoenix, Arizona, USA"},
    {"name": "us-sanjose-1", "location": "San Jose, California, USA"},
    {"name": "us-chicago-1", "location": "Chicago, Illinois, USA"},
    {"name": "ca-toronto-1", "location": "Toronto, Canada"},
    {"name": "ca-montreal-1", "location": "Montreal, Canada"},
    {"name": "eu-frankfurt-1", "location": "Frankfurt, Germany"},
    {"name": "eu-amsterdam-1", "location": "Amsterdam, Netherlands"},
    {"name": "eu-zurich-1", "location": "Zurich, Switzerland"},
    {"name": "eu-madrid-1", "location": "Madrid, Spain"},
    {"name": "eu-marseille-1", "location": "Marseille, France"},
    {"name": "eu-milan-1", "location": "Milan, Italy"},
    {"name": "eu-stockholm-1", "location": "Stockholm, Sweden"},
    {"name": "eu-paris-1", "location": "Paris, France"},
    {"name": "uk-london-1", "location": "London, UK"},
    {"name": "uk-cardiff-1", "location": "Cardiff, UK"},
    {"name": "ap-tokyo-1", "location": "Tokyo, Japan"},
    {"name": "ap-osaka-1", "location": "Osaka, Japan"},
    {"name": "ap-seoul-1", "location": "Seoul, South Korea"},
    {"name": "ap-chuncheon-1", "location": "Chuncheon, South Korea"},
    {"name": "ap-mumbai-1", "location": "Mumbai, India"},
    {"name": "ap-hyderabad-1", "location": "Hyderabad, India"},
    {"name": "ap-singapore-1", "location": "Singapore"},
    {"name": "ap-sydney-1", "location": "Sydney, Australia"},
    {"name": "ap-melbourne-1", "location": "Melbourne, Australia"},
    {"name": "sa-saopaulo-1", "location": "Sao Paulo, Brazil"},
    {"name": "sa-vinhedo-1", "location": "Vinhedo, Brazil"},
    {"name": "me-jeddah-1", "location": "Jeddah, Saudi Arabia"},
    {"name": "me-dubai-1", "location": "Dubai, UAE"},
    {"name": "af-johannesburg-1", "location": "Johannesburg, South Africa"},
    {"name": "il-jerusalem-1", "location": "Jerusalem, Israel"},
]

# Free tier eligible shapes
FREE_TIER_SHAPES = [
    {
        "name": "VM.Standard.A1.Flex",
        "type": "ARM (Ampere)",
        "free_ocpus": 4,
        "free_memory_gb": 24,
        "notes": "Best free tier option. 4 OCPUs and 24GB RAM total across all A1 instances."
    },
    {
        "name": "VM.Standard.E2.1.Micro",
        "type": "AMD x86",
        "free_ocpus": 1,
        "free_memory_gb": 1,
        "notes": "Micro instance. 2 instances always free."
    },
]


def speak(message: str):
    """Print message clearly for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp for lists."""
    print(message)
    sys.stdout.flush()


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    path = Path(config_path).expanduser()
    if not path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    with open(path) as f:
        return json.load(f)


def get_oci_config(profile: str = "DEFAULT") -> dict:
    """Load OCI SDK configuration from ~/.oci/config."""
    config_path = Path.home() / ".oci" / "config"
    if not config_path.exists():
        print(f"Error: OCI config not found at {config_path}")
        print("Run 'oci setup config' to create it.")
        sys.exit(1)

    return oci.config.from_file(profile_name=profile)


def list_regions():
    """List all Oracle Cloud regions."""
    speak_plain("")
    speak_plain("Oracle Cloud Regions")
    speak_plain("=" * 60)
    speak_plain("")

    for region in OCI_REGIONS:
        speak_plain(f"  {region['name']}")
        speak_plain(f"    Location: {region['location']}")
        speak_plain("")

    speak_plain(f"Total: {len(OCI_REGIONS)} regions")
    speak_plain("")
    speak_plain("Tip: Try regions geographically closer to you first.")
    speak_plain("Popular regions like us-ashburn-1 are often out of capacity.")


def list_shapes():
    """List free tier eligible shapes."""
    speak_plain("")
    speak_plain("Oracle Cloud Free Tier Shapes")
    speak_plain("=" * 60)
    speak_plain("")

    for shape in FREE_TIER_SHAPES:
        speak_plain(f"  Shape: {shape['name']}")
        speak_plain(f"    Type: {shape['type']}")
        speak_plain(f"    Free OCPUs: {shape['free_ocpus']}")
        speak_plain(f"    Free Memory: {shape['free_memory_gb']} GB")
        speak_plain(f"    Notes: {shape['notes']}")
        speak_plain("")

    speak_plain("Recommendation: Use VM.Standard.A1.Flex for the best free resources.")


def list_compartments(profile: str = "DEFAULT"):
    """List available compartments."""
    speak("Fetching compartments from Oracle Cloud...")

    try:
        oci_config = get_oci_config(profile)
        identity_client = oci.identity.IdentityClient(oci_config)

        # Get tenancy ID
        tenancy_id = oci_config["tenancy"]

        # List compartments
        response = identity_client.list_compartments(
            compartment_id=tenancy_id,
            compartment_id_in_subtree=True,
            lifecycle_state="ACTIVE"
        )

        speak_plain("")
        speak_plain("Available Compartments")
        speak_plain("=" * 60)
        speak_plain("")

        # Root compartment (tenancy)
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
        speak_plain("")
        speak_plain("Copy the ID of your target compartment into your config file.")

    except oci.exceptions.ServiceError as e:
        print(f"Error fetching compartments: {e.message}")
        sys.exit(1)


def export_config(output_path: str):
    """Export a template configuration file."""
    template = {
        "_comment": "OCI Free Instance Configuration File",
        "_instructions": [
            "1. Get your compartment_id using: python3 oci_free_instance.py --compartments",
            "2. Add your SSH public key (cat ~/.ssh/id_rsa.pub)",
            "3. Optionally customize shape, ocpus, memory_gb",
            "4. Add regions to try in order of preference"
        ],
        "compartment_id": "ocid1.compartment.oc1..your-compartment-id-here",
        "ssh_public_key": "ssh-rsa AAAA... your-key-here",
        "shape": "VM.Standard.A1.Flex",
        "ocpus": 4,
        "memory_gb": 24,
        "instance_name": "free-arm-instance",
        "retry_interval_seconds": 60,
        "max_attempts": 0,
        "regions": [
            "us-ashburn-1",
            "us-phoenix-1",
            "eu-frankfurt-1"
        ],
        "oci_profile": "DEFAULT"
    }

    path = Path(output_path).expanduser()
    with open(path, 'w') as f:
        json.dump(template, f, indent=2)

    speak_plain(f"Configuration template exported to: {output_path}")
    speak_plain("")
    speak_plain("Next steps:")
    speak_plain("  1. Run: python3 oci_free_instance.py --compartments")
    speak_plain("  2. Copy your compartment ID into the config file")
    speak_plain("  3. Add your SSH public key (cat ~/.ssh/id_rsa.pub)")
    speak_plain("  4. Run: python3 oci_free_instance.py --config " + output_path)


def import_config(input_path: str) -> dict:
    """Import and validate a configuration file."""
    config = load_config(input_path)

    speak("Validating configuration...")

    # Required fields
    required = ["compartment_id"]
    for field in required:
        if field not in config or not config[field]:
            print(f"Error: Required field '{field}' is missing or empty.")
            sys.exit(1)
        if "your-" in str(config[field]) or "here" in str(config[field]):
            print(f"Error: Field '{field}' still contains placeholder text.")
            print(f"  Current value: {config[field]}")
            sys.exit(1)

    # Warnings
    if "ssh_public_key" not in config or not config["ssh_public_key"]:
        speak("Warning: No SSH public key configured. You won't be able to SSH into the instance.")
    elif "your-key" in config["ssh_public_key"]:
        print("Error: SSH public key contains placeholder text.")
        sys.exit(1)

    speak("Configuration is valid.")
    return config


def list_availability_domains(identity_client, compartment_id: str) -> list:
    """Get all availability domains in the compartment."""
    response = identity_client.list_availability_domains(compartment_id)
    return [ad.name for ad in response.data]


def get_ubuntu_image(compute_client, compartment_id: str, shape: str) -> str:
    """Find the latest Ubuntu image compatible with the shape."""
    speak("Finding Ubuntu image for the selected shape...")

    response = compute_client.list_images(
        compartment_id=compartment_id,
        operating_system="Canonical Ubuntu",
        shape=shape,
        sort_by="TIMECREATED",
        sort_order="DESC"
    )

    if not response.data:
        print("Error: No Ubuntu images found for this shape.")
        sys.exit(1)

    image = response.data[0]
    speak(f"Using image: {image.display_name}")
    return image.id


def get_subnet(network_client, compartment_id: str, vcn_id: str = None) -> str:
    """Get or create a subnet for the instance."""
    # List existing subnets
    response = network_client.list_subnets(compartment_id=compartment_id)

    if response.data:
        subnet = response.data[0]
        speak(f"Using existing subnet: {subnet.display_name}")
        return subnet.id

    print("Error: No subnet found. Please create a VCN and subnet first.")
    print("You can do this in the Oracle Cloud Console under Networking > Virtual Cloud Networks.")
    sys.exit(1)


def attempt_launch(compute_client, config: dict, availability_domain: str,
                   image_id: str, subnet_id: str, attempt: int) -> tuple:
    """
    Attempt to launch an instance.
    Returns (success: bool, instance_id or error_message: str)
    """
    shape = config.get("shape", "VM.Standard.A1.Flex")
    ocpus = config.get("ocpus", 4)
    memory_gb = config.get("memory_gb", 24)
    display_name = config.get("instance_name", "free-instance")

    # Build instance details
    instance_details = oci.core.models.LaunchInstanceDetails(
        availability_domain=availability_domain,
        compartment_id=config["compartment_id"],
        shape=shape,
        display_name=display_name,
        image_id=image_id,
        subnet_id=subnet_id,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=float(ocpus),
            memory_in_gbs=float(memory_gb)
        ),
        metadata={
            "ssh_authorized_keys": config.get("ssh_public_key", "")
        },
        is_pv_encryption_in_transit_enabled=True
    )

    try:
        response = compute_client.launch_instance(instance_details)
        return True, response.data.id
    except oci.exceptions.ServiceError as e:
        return False, f"{e.code}: {e.message}"


def run_retry_loop(config: dict, region: str = None):
    """Main retry loop to acquire an instance."""
    # Load OCI SDK config
    oci_config = get_oci_config(config.get("oci_profile", "DEFAULT"))

    # Override region if specified
    if region:
        oci_config["region"] = region

    speak(f"Starting instance acquisition in region: {oci_config['region']}")
    speak(f"Target shape: {config.get('shape', 'VM.Standard.A1.Flex')}")
    speak(f"OCPUs: {config.get('ocpus', 4)}, Memory: {config.get('memory_gb', 24)} GB")

    # Initialize clients
    identity_client = oci.identity.IdentityClient(oci_config)
    compute_client = oci.core.ComputeClient(oci_config)
    network_client = oci.core.VirtualNetworkClient(oci_config)

    compartment_id = config["compartment_id"]

    # Get availability domains
    speak("Fetching availability domains...")
    availability_domains = list_availability_domains(identity_client, compartment_id)
    speak(f"Found {len(availability_domains)} availability domains.")

    # Get image
    image_id = config.get("image_id")
    if not image_id:
        image_id = get_ubuntu_image(compute_client, compartment_id,
                                     config.get("shape", "VM.Standard.A1.Flex"))

    # Get subnet
    subnet_id = config.get("subnet_id")
    if not subnet_id:
        subnet_id = get_subnet(network_client, compartment_id)

    # Retry settings
    retry_interval = config.get("retry_interval_seconds", 60)
    max_attempts = config.get("max_attempts", 0)  # 0 = infinite

    speak(f"Retry interval: {retry_interval} seconds")
    if max_attempts > 0:
        speak(f"Maximum attempts: {max_attempts}")
    else:
        speak("Will retry indefinitely until successful. Press Ctrl+C to stop.")

    speak("")
    speak("Starting launch attempts...")
    speak("")

    attempt = 0
    ad_index = 0

    while True:
        attempt += 1
        current_ad = availability_domains[ad_index]

        speak(f"Attempt {attempt}: Trying availability domain {current_ad}")

        success, result = attempt_launch(
            compute_client, config, current_ad, image_id, subnet_id, attempt
        )

        if success:
            speak("")
            speak("SUCCESS! Instance launched!")
            speak(f"Instance ID: {result}")
            speak("Check the Oracle Cloud Console for your new instance.")
            speak("It may take a few minutes to fully provision.")
            return True

        # Check if we should stop
        if "Out of host capacity" in result or "Out of capacity" in result:
            speak(f"No capacity available. Will retry in {retry_interval} seconds.")
        elif "LimitExceeded" in result:
            speak("Resource limit exceeded. You may already have an instance.")
            speak("Check your existing instances in the Oracle Cloud Console.")
            return False
        elif "NotAuthorized" in result or "401" in result:
            speak("Authentication error. Check your OCI credentials.")
            return False
        else:
            speak(f"Launch failed: {result}")
            speak(f"Will retry in {retry_interval} seconds.")

        # Check max attempts
        if max_attempts > 0 and attempt >= max_attempts:
            speak(f"Reached maximum attempts ({max_attempts}). Stopping.")
            return False

        # Rotate through availability domains
        ad_index = (ad_index + 1) % len(availability_domains)

        # Wait before retry
        speak(f"Waiting {retry_interval} seconds...")
        time.sleep(retry_interval)
        speak("")


def run_multi_region(config: dict):
    """Try multiple regions in sequence."""
    regions = config.get("regions", [])

    if not regions:
        print("Error: No regions specified in config.")
        print("Add a 'regions' list to your config, or use --export-config to generate a template.")
        sys.exit(1)

    speak(f"Will try {len(regions)} regions: {', '.join(regions)}")
    speak("")

    for region in regions:
        speak(f"Trying region: {region}")
        speak("")

        if run_retry_loop(config, region):
            return True

        speak(f"Region {region} exhausted. Moving to next region.")
        speak("")

    speak("All regions tried. No instance acquired.")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Retry launching Oracle Cloud free tier instance until successful.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List available options:
    python3 oci_free_instance.py --regions
    python3 oci_free_instance.py --shapes
    python3 oci_free_instance.py --compartments

    # Create a config file:
    python3 oci_free_instance.py --export-config my-config.json

    # Run the retry loop:
    python3 oci_free_instance.py --config my-config.json
    python3 oci_free_instance.py --config my-config.json --region us-phoenix-1
    python3 oci_free_instance.py --config my-config.json --multi-region

For screen reader users:
    All output is plain text with timestamps.
    Press Ctrl+C at any time to stop the script.
    Success and failure are announced clearly.
"""
    )

    # Discovery options
    discovery = parser.add_argument_group("Discovery Options")
    discovery.add_argument(
        "--regions",
        action="store_true",
        help="List all Oracle Cloud regions"
    )
    discovery.add_argument(
        "--shapes",
        action="store_true",
        help="List free tier eligible shapes"
    )
    discovery.add_argument(
        "--compartments",
        action="store_true",
        help="List compartments in your account (requires OCI config)"
    )

    # Config options
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument(
        "--export-config",
        metavar="FILE",
        help="Export a template configuration file"
    )
    config_group.add_argument(
        "--import-config", "--config", "-c",
        metavar="FILE",
        dest="config",
        help="Path to JSON configuration file"
    )
    config_group.add_argument(
        "--profile", "-p",
        default="DEFAULT",
        help="OCI config profile to use (default: DEFAULT)"
    )

    # Run options
    run_group = parser.add_argument_group("Run Options")
    run_group.add_argument(
        "--region", "-r",
        help="Override region from config (e.g., us-ashburn-1)"
    )
    run_group.add_argument(
        "--multi-region", "-m",
        action="store_true",
        help="Try all regions listed in config file"
    )

    args = parser.parse_args()

    # Handle discovery options
    if args.regions:
        list_regions()
        sys.exit(0)

    if args.shapes:
        list_shapes()
        sys.exit(0)

    if args.compartments:
        list_compartments(args.profile)
        sys.exit(0)

    # Handle config export
    if args.export_config:
        export_config(args.export_config)
        sys.exit(0)

    # Require config for actual run
    if not args.config:
        parser.print_help()
        print("\nError: --config is required to run the instance acquisition.")
        print("Use --export-config to create a template configuration file.")
        sys.exit(1)

    speak("Oracle Cloud Free Instance Acquisition Script")
    speak("Designed for accessibility with screen readers")
    speak("")

    # Load and validate config
    config = import_config(args.config)

    try:
        if args.multi_region:
            success = run_multi_region(config)
        else:
            success = run_retry_loop(config, args.region)

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        speak("")
        speak("Script stopped by user. Goodbye.")
        sys.exit(0)
    except Exception as e:
        speak(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
