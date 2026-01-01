#!/usr/bin/env python3
"""
Oracle Cloud to Terraform Generator

Reads Oracle Cloud configuration and generates Terraform HCL files.
Designed for accessibility with screen reader friendly output.

Usage:
    generate_terraform.py --compartment ocid... --output ./terraform
    generate_terraform.py --config oci-export.json --output ./terraform
    generate_terraform.py --all --output ./terraform    # Export everything
    generate_terraform.py --resources compute,network   # Specific resources
"""

import argparse
import json
import os
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


def sanitize_name(name: str) -> str:
    """Convert name to valid Terraform resource name."""
    # Replace invalid characters with underscores
    result = ""
    for char in name.lower():
        if char.isalnum() or char == "_":
            result += char
        else:
            result += "_"
    # Remove consecutive underscores
    while "__" in result:
        result = result.replace("__", "_")
    # Remove leading/trailing underscores
    return result.strip("_")


def generate_provider_block(config: dict) -> str:
    """Generate Terraform OCI provider block."""
    return f'''# Oracle Cloud Infrastructure Provider
# Configure authentication via environment variables or OCI config file

terraform {{
  required_providers {{
    oci = {{
      source  = "oracle/oci"
      version = "~> 5.0"
    }}
  }}
}}

provider "oci" {{
  # Authentication options:
  # Option 1: Use OCI config file (default)
  # config_file_profile = "DEFAULT"

  # Option 2: Use environment variables
  # tenancy_ocid     = var.tenancy_ocid
  # user_ocid        = var.user_ocid
  # fingerprint      = var.fingerprint
  # private_key_path = var.private_key_path
  # region           = var.region

  region = "{config.get('region', 'us-ashburn-1')}"
}}

# Variables for OCI authentication
variable "tenancy_ocid" {{
  description = "OCID of the tenancy"
  type        = string
  default     = "{config.get('tenancy', '')}"
}}

variable "compartment_ocid" {{
  description = "OCID of the compartment"
  type        = string
}}

variable "region" {{
  description = "OCI region"
  type        = string
  default     = "{config.get('region', 'us-ashburn-1')}"
}}
'''


def export_vcn(network_client, compartment_id: str) -> list:
    """Export VCN resources to Terraform."""
    resources = []

    speak("Exporting VCNs...")
    vcns = network_client.list_vcns(compartment_id=compartment_id).data

    for vcn in vcns:
        name = sanitize_name(vcn.display_name)
        resource = f'''
# VCN: {vcn.display_name}
resource "oci_core_vcn" "{name}" {{
  compartment_id = var.compartment_ocid
  display_name   = "{vcn.display_name}"
  cidr_blocks    = {json.dumps(vcn.cidr_blocks)}
  dns_label      = "{vcn.dns_label or ''}"

  freeform_tags = {json.dumps(vcn.freeform_tags or {{}})}
}}

# Output VCN ID
output "{name}_vcn_id" {{
  value = oci_core_vcn.{name}.id
}}
'''
        resources.append(resource)

        # Export subnets for this VCN
        subnets = network_client.list_subnets(
            compartment_id=compartment_id,
            vcn_id=vcn.id
        ).data

        for subnet in subnets:
            subnet_name = sanitize_name(subnet.display_name)
            subnet_resource = f'''
# Subnet: {subnet.display_name}
resource "oci_core_subnet" "{subnet_name}" {{
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.{name}.id
  display_name      = "{subnet.display_name}"
  cidr_block        = "{subnet.cidr_block}"
  dns_label         = "{subnet.dns_label or ''}"
  prohibit_public_ip_on_vnic = {str(subnet.prohibit_public_ip_on_vnic).lower()}

  freeform_tags = {json.dumps(subnet.freeform_tags or {{}})}
}}
'''
            resources.append(subnet_resource)

        # Export internet gateway
        igws = network_client.list_internet_gateways(
            compartment_id=compartment_id,
            vcn_id=vcn.id
        ).data

        for igw in igws:
            igw_name = sanitize_name(igw.display_name)
            igw_resource = f'''
# Internet Gateway: {igw.display_name}
resource "oci_core_internet_gateway" "{igw_name}" {{
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.{name}.id
  display_name   = "{igw.display_name}"
  enabled        = {str(igw.is_enabled).lower()}
}}
'''
            resources.append(igw_resource)

    speak(f"  Exported {len(vcns)} VCNs")
    return resources


def export_compute(compute_client, compartment_id: str) -> list:
    """Export compute instances to Terraform."""
    resources = []

    speak("Exporting compute instances...")
    instances = compute_client.list_instances(compartment_id=compartment_id).data

    active_instances = [i for i in instances if i.lifecycle_state not in ["TERMINATED", "TERMINATING"]]

    for instance in active_instances:
        name = sanitize_name(instance.display_name)

        # Get shape config for flex shapes
        shape_config = ""
        if instance.shape_config:
            shape_config = f'''
  shape_config {{
    ocpus         = {instance.shape_config.ocpus}
    memory_in_gbs = {instance.shape_config.memory_in_gbs}
  }}'''

        # Get boot volume details
        boot_vols = compute_client.list_boot_volume_attachments(
            availability_domain=instance.availability_domain,
            compartment_id=compartment_id,
            instance_id=instance.id
        ).data

        source_details = ""
        if boot_vols:
            bv = boot_vols[0]
            source_details = f'''
  source_details {{
    source_type = "bootVolume"
    source_id   = "{bv.boot_volume_id}"
  }}'''

        resource = f'''
# Compute Instance: {instance.display_name}
resource "oci_core_instance" "{name}" {{
  compartment_id      = var.compartment_ocid
  availability_domain = "{instance.availability_domain}"
  display_name        = "{instance.display_name}"
  shape               = "{instance.shape}"
  {shape_config}
  {source_details}

  # Note: VNIC and metadata configuration may need manual adjustment
  # based on your specific requirements

  freeform_tags = {json.dumps(instance.freeform_tags or {{}})}
}}

output "{name}_instance_id" {{
  value = oci_core_instance.{name}.id
}}
'''
        resources.append(resource)

    speak(f"  Exported {len(active_instances)} compute instances")
    return resources


def export_block_storage(blockstorage_client, compartment_id: str) -> list:
    """Export block volumes to Terraform."""
    resources = []

    speak("Exporting block volumes...")
    volumes = blockstorage_client.list_volumes(compartment_id=compartment_id).data

    active_volumes = [v for v in volumes if v.lifecycle_state == "AVAILABLE"]

    for volume in active_volumes:
        name = sanitize_name(volume.display_name)

        resource = f'''
# Block Volume: {volume.display_name}
resource "oci_core_volume" "{name}" {{
  compartment_id      = var.compartment_ocid
  availability_domain = "{volume.availability_domain}"
  display_name        = "{volume.display_name}"
  size_in_gbs         = {volume.size_in_gbs}
  vpus_per_gb         = {volume.vpus_per_gb or 10}

  freeform_tags = {json.dumps(volume.freeform_tags or {{}})}
}}

output "{name}_volume_id" {{
  value = oci_core_volume.{name}.id
}}
'''
        resources.append(resource)

    speak(f"  Exported {len(active_volumes)} block volumes")
    return resources


def export_object_storage(object_storage_client, namespace: str, compartment_id: str) -> list:
    """Export object storage buckets to Terraform."""
    resources = []

    speak("Exporting object storage buckets...")
    buckets = object_storage_client.list_buckets(
        namespace_name=namespace,
        compartment_id=compartment_id
    ).data

    for bucket in buckets:
        name = sanitize_name(bucket.name)

        resource = f'''
# Object Storage Bucket: {bucket.name}
resource "oci_objectstorage_bucket" "{name}" {{
  compartment_id = var.compartment_ocid
  namespace      = "{namespace}"
  name           = "{bucket.name}"
  access_type    = "NoPublicAccess"

  # Note: Additional settings like versioning, lifecycle rules
  # may need to be configured based on bucket details

  freeform_tags = {json.dumps(bucket.freeform_tags or {{}})}
}}

output "{name}_bucket_name" {{
  value = oci_objectstorage_bucket.{name}.name
}}
'''
        resources.append(resource)

    speak(f"  Exported {len(buckets)} buckets")
    return resources


def export_load_balancers(lb_client, compartment_id: str) -> list:
    """Export load balancers to Terraform."""
    resources = []

    speak("Exporting load balancers...")
    lbs = lb_client.list_load_balancers(compartment_id=compartment_id).data

    active_lbs = [lb for lb in lbs if lb.lifecycle_state == "ACTIVE"]

    for lb in active_lbs:
        name = sanitize_name(lb.display_name)

        subnet_ids = json.dumps(lb.subnet_ids) if lb.subnet_ids else '[]'

        resource = f'''
# Load Balancer: {lb.display_name}
resource "oci_load_balancer_load_balancer" "{name}" {{
  compartment_id = var.compartment_ocid
  display_name   = "{lb.display_name}"
  shape          = "{lb.shape_name}"
  subnet_ids     = {subnet_ids}
  is_private     = {str(lb.is_private).lower()}

  # Note: Backend sets, listeners, and certificates need manual configuration

  freeform_tags = {json.dumps(lb.freeform_tags or {{}})}
}}

output "{name}_lb_ip" {{
  value = oci_load_balancer_load_balancer.{name}.ip_addresses
}}
'''
        resources.append(resource)

    speak(f"  Exported {len(active_lbs)} load balancers")
    return resources


def run_export(args):
    """Run the Terraform export."""
    speak("Oracle Cloud to Terraform Export")
    speak("")

    oci_config = get_oci_config(args.profile)
    compartment_id = args.compartment or oci_config["tenancy"]

    speak(f"Compartment: {compartment_id}")
    speak(f"Output directory: {args.output}")
    speak("")

    # Create output directory
    output_path = Path(args.output).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize clients
    compute_client = oci.core.ComputeClient(oci_config)
    network_client = oci.core.VirtualNetworkClient(oci_config)
    blockstorage_client = oci.core.BlockstorageClient(oci_config)
    object_storage_client = oci.object_storage.ObjectStorageClient(oci_config)
    lb_client = oci.load_balancer.LoadBalancerClient(oci_config)

    # Get object storage namespace
    namespace = object_storage_client.get_namespace().data

    # Determine which resources to export
    resource_types = args.resources.split(",") if args.resources else [
        "network", "compute", "storage", "objectstorage", "loadbalancer"
    ]

    all_resources = []

    try:
        # Export based on selected resource types
        if "network" in resource_types or args.all:
            all_resources.extend(export_vcn(network_client, compartment_id))

        if "compute" in resource_types or args.all:
            all_resources.extend(export_compute(compute_client, compartment_id))

        if "storage" in resource_types or args.all:
            all_resources.extend(export_block_storage(blockstorage_client, compartment_id))

        if "objectstorage" in resource_types or args.all:
            all_resources.extend(export_object_storage(object_storage_client, namespace, compartment_id))

        if "loadbalancer" in resource_types or args.all:
            all_resources.extend(export_load_balancers(lb_client, compartment_id))

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)

    # Write provider file
    provider_content = generate_provider_block(oci_config)
    provider_file = output_path / "provider.tf"
    with open(provider_file, "w") as f:
        f.write(provider_content)
    speak(f"Written: {provider_file}")

    # Write main resources file
    main_content = "# Oracle Cloud Infrastructure Resources\n"
    main_content += "# Generated by generate_terraform.py\n"
    main_content += f"# Generated at: {datetime.now().isoformat()}\n\n"
    main_content += "\n".join(all_resources)

    main_file = output_path / "main.tf"
    with open(main_file, "w") as f:
        f.write(main_content)
    speak(f"Written: {main_file}")

    # Write terraform.tfvars template
    tfvars_content = f'''# Terraform Variables
# Edit these values for your environment

tenancy_ocid    = "{oci_config.get('tenancy', '')}"
compartment_ocid = "{compartment_id}"
region          = "{oci_config.get('region', 'us-ashburn-1')}"
'''

    tfvars_file = output_path / "terraform.tfvars.example"
    with open(tfvars_file, "w") as f:
        f.write(tfvars_content)
    speak(f"Written: {tfvars_file}")

    speak("")
    speak("Export complete!")
    speak_plain("")
    speak_plain("Next steps:")
    speak_plain(f"  1. cd {args.output}")
    speak_plain("  2. Review and modify the generated .tf files")
    speak_plain("  3. Copy terraform.tfvars.example to terraform.tfvars")
    speak_plain("  4. Run: terraform init")
    speak_plain("  5. Run: terraform plan")
    speak_plain("")
    speak_plain("Note: Some resources may need manual adjustment.")
    speak_plain("Review the generated files carefully before applying.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Terraform from Oracle Cloud resources. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    generate_terraform.py --output ./terraform
    generate_terraform.py --compartment ocid1... --output ./terraform
    generate_terraform.py --resources compute,network --output ./terraform
    generate_terraform.py --all --output ./terraform

Resource Types:
    network      - VCNs, subnets, internet gateways
    compute      - Compute instances
    storage      - Block volumes
    objectstorage - Object storage buckets
    loadbalancer - Load balancers

Screen Reader Notes:
    Progress messages include timestamps.
    Output files are listed as they are created.
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
    parser.add_argument(
        "--output", "-o",
        default="./terraform",
        help="Output directory (default: ./terraform)"
    )
    parser.add_argument(
        "--resources", "-r",
        help="Comma-separated list of resource types to export"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Export all resource types"
    )

    args = parser.parse_args()

    try:
        run_export(args)
    except KeyboardInterrupt:
        speak("")
        speak("Export cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
