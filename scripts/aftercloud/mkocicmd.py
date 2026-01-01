#!/usr/bin/env python3
"""
OCI Command Generator

Interactive utility to help generate Oracle Cloud CLI commands.
Designed for accessibility with screen reader friendly output.

Usage:
    mkocicmd.py                           # Interactive mode
    mkocicmd.py compute                   # Compute commands
    mkocicmd.py network                   # Network commands
    mkocicmd.py storage                   # Storage commands
    mkocicmd.py iam                       # IAM commands
    mkocicmd.py db                        # Database commands
    mkocicmd.py container                 # Container commands
"""

import argparse
import sys
from datetime import datetime


def speak(message: str):
    """Print message with timestamp for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


def print_command(command: str, description: str):
    """Print a command with its description."""
    speak_plain("")
    speak_plain(f"  {description}")
    speak_plain(f"    {command}")


def print_category(title: str):
    """Print category header."""
    speak_plain("")
    speak_plain("=" * 70)
    speak_plain(f"  {title}")
    speak_plain("=" * 70)


def compute_commands(args):
    """Generate compute commands."""
    print_category("Compute Instance Commands")

    speak_plain("")
    speak_plain("Common Variables (set these first):")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")
    speak_plain("  export AD='AD-1'  # Availability Domain")
    speak_plain("  export SUBNET_ID='ocid1.subnet.oc1...'")

    print_command(
        "oci compute instance list --compartment-id $COMPARTMENT_ID",
        "List all instances in compartment"
    )

    print_command(
        "oci compute instance list --compartment-id $COMPARTMENT_ID --lifecycle-state RUNNING",
        "List only running instances"
    )

    print_command(
        "oci compute instance get --instance-id <instance-ocid>",
        "Get instance details"
    )

    print_command(
        "oci compute instance action --instance-id <instance-ocid> --action START",
        "Start an instance"
    )

    print_command(
        "oci compute instance action --instance-id <instance-ocid> --action STOP",
        "Stop an instance (graceful)"
    )

    print_command(
        "oci compute instance action --instance-id <instance-ocid> --action SOFTRESET",
        "Reboot an instance (graceful)"
    )

    print_command(
        "oci compute instance action --instance-id <instance-ocid> --action RESET",
        "Force reboot an instance"
    )

    print_command(
        "oci compute instance terminate --instance-id <instance-ocid> --force",
        "Terminate instance (WARNING: permanent)"
    )

    print_command(
        """oci compute instance launch \\
    --compartment-id $COMPARTMENT_ID \\
    --availability-domain $AD \\
    --shape 'VM.Standard.A1.Flex' \\
    --shape-config '{"ocpus": 1, "memoryInGBs": 6}' \\
    --display-name 'my-instance' \\
    --image-id <image-ocid> \\
    --subnet-id $SUBNET_ID \\
    --assign-public-ip true \\
    --ssh-authorized-keys-file ~/.ssh/id_rsa.pub""",
        "Launch a new ARM instance"
    )

    print_command(
        "oci compute image list --compartment-id $COMPARTMENT_ID --operating-system 'Canonical Ubuntu' --shape 'VM.Standard.A1.Flex'",
        "List Ubuntu images for ARM shape"
    )

    print_command(
        "oci compute shape list --compartment-id $COMPARTMENT_ID",
        "List available shapes"
    )

    print_command(
        "oci compute instance list-vnics --instance-id <instance-ocid>",
        "List instance network interfaces"
    )

    print_command(
        "oci compute instance get-windows-initial-creds --instance-id <instance-ocid>",
        "Get Windows instance initial password"
    )


def network_commands(args):
    """Generate network commands."""
    print_category("Network Commands")

    speak_plain("")
    speak_plain("Common Variables:")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")
    speak_plain("  export VCN_ID='ocid1.vcn.oc1...'")

    # VCN
    speak_plain("")
    speak_plain("--- Virtual Cloud Network (VCN) ---")

    print_command(
        "oci network vcn list --compartment-id $COMPARTMENT_ID",
        "List all VCNs"
    )

    print_command(
        """oci network vcn create \\
    --compartment-id $COMPARTMENT_ID \\
    --cidr-blocks '["10.0.0.0/16"]' \\
    --display-name 'my-vcn' \\
    --dns-label 'myvcn'""",
        "Create a new VCN"
    )

    print_command(
        "oci network vcn delete --vcn-id $VCN_ID --force",
        "Delete a VCN"
    )

    # Subnets
    speak_plain("")
    speak_plain("--- Subnets ---")

    print_command(
        "oci network subnet list --compartment-id $COMPARTMENT_ID --vcn-id $VCN_ID",
        "List subnets in VCN"
    )

    print_command(
        """oci network subnet create \\
    --compartment-id $COMPARTMENT_ID \\
    --vcn-id $VCN_ID \\
    --cidr-block '10.0.1.0/24' \\
    --display-name 'public-subnet' \\
    --dns-label 'public'""",
        "Create a public subnet"
    )

    # Internet Gateway
    speak_plain("")
    speak_plain("--- Internet Gateway ---")

    print_command(
        "oci network internet-gateway list --compartment-id $COMPARTMENT_ID --vcn-id $VCN_ID",
        "List internet gateways"
    )

    print_command(
        """oci network internet-gateway create \\
    --compartment-id $COMPARTMENT_ID \\
    --vcn-id $VCN_ID \\
    --is-enabled true \\
    --display-name 'igw'""",
        "Create internet gateway"
    )

    # Security Lists
    speak_plain("")
    speak_plain("--- Security Lists ---")

    print_command(
        "oci network security-list list --compartment-id $COMPARTMENT_ID --vcn-id $VCN_ID",
        "List security lists"
    )

    print_command(
        """oci network security-list update \\
    --security-list-id <seclist-ocid> \\
    --ingress-security-rules '[{
        "source": "0.0.0.0/0",
        "protocol": "6",
        "tcpOptions": {"destinationPortRange": {"min": 22, "max": 22}}
    }]'""",
        "Add SSH ingress rule"
    )

    # Public IPs
    speak_plain("")
    speak_plain("--- Public IPs ---")

    print_command(
        "oci network public-ip list --compartment-id $COMPARTMENT_ID --scope REGION --lifetime RESERVED",
        "List reserved public IPs"
    )

    print_command(
        """oci network public-ip create \\
    --compartment-id $COMPARTMENT_ID \\
    --lifetime RESERVED \\
    --display-name 'my-reserved-ip'""",
        "Create reserved public IP"
    )


def storage_commands(args):
    """Generate storage commands."""
    print_category("Storage Commands")

    speak_plain("")
    speak_plain("Common Variables:")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")
    speak_plain("  export AD='AD-1'")
    speak_plain("  export NAMESPACE='your-namespace'  # Get with: oci os ns get")

    # Block Storage
    speak_plain("")
    speak_plain("--- Block Storage ---")

    print_command(
        "oci bv volume list --compartment-id $COMPARTMENT_ID",
        "List block volumes"
    )

    print_command(
        """oci bv volume create \\
    --compartment-id $COMPARTMENT_ID \\
    --availability-domain $AD \\
    --display-name 'my-volume' \\
    --size-in-gbs 100 \\
    --vpus-per-gb 10""",
        "Create 100GB block volume (balanced performance)"
    )

    print_command(
        "oci compute volume-attachment attach --instance-id <instance-ocid> --volume-id <volume-ocid> --type paravirtualized",
        "Attach volume to instance"
    )

    print_command(
        "oci compute volume-attachment detach --volume-attachment-id <attachment-ocid>",
        "Detach volume from instance"
    )

    print_command(
        "oci bv volume update --volume-id <volume-ocid> --size-in-gbs 200",
        "Resize volume to 200GB"
    )

    # Backups
    speak_plain("")
    speak_plain("--- Volume Backups ---")

    print_command(
        "oci bv backup list --compartment-id $COMPARTMENT_ID",
        "List volume backups"
    )

    print_command(
        """oci bv backup create \\
    --volume-id <volume-ocid> \\
    --display-name 'my-backup' \\
    --type INCREMENTAL""",
        "Create incremental backup"
    )

    # Object Storage
    speak_plain("")
    speak_plain("--- Object Storage ---")

    print_command(
        "oci os ns get",
        "Get object storage namespace"
    )

    print_command(
        "oci os bucket list --compartment-id $COMPARTMENT_ID --namespace-name $NAMESPACE",
        "List buckets"
    )

    print_command(
        """oci os bucket create \\
    --compartment-id $COMPARTMENT_ID \\
    --namespace-name $NAMESPACE \\
    --name 'my-bucket' \\
    --public-access-type NoPublicAccess""",
        "Create private bucket"
    )

    print_command(
        "oci os object put --bucket-name 'my-bucket' --namespace-name $NAMESPACE --file ./local-file.txt",
        "Upload file to bucket"
    )

    print_command(
        "oci os object list --bucket-name 'my-bucket' --namespace-name $NAMESPACE",
        "List objects in bucket"
    )

    print_command(
        "oci os object get --bucket-name 'my-bucket' --namespace-name $NAMESPACE --name 'file.txt' --file ./downloaded.txt",
        "Download file from bucket"
    )


def iam_commands(args):
    """Generate IAM commands."""
    print_category("IAM Commands")

    speak_plain("")
    speak_plain("Common Variables:")
    speak_plain("  export TENANCY_ID='ocid1.tenancy.oc1...'")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")

    # Compartments
    speak_plain("")
    speak_plain("--- Compartments ---")

    print_command(
        "oci iam compartment list --compartment-id $TENANCY_ID",
        "List all compartments"
    )

    print_command(
        """oci iam compartment create \\
    --compartment-id $TENANCY_ID \\
    --name 'my-compartment' \\
    --description 'Development compartment'""",
        "Create compartment"
    )

    # Users
    speak_plain("")
    speak_plain("--- Users ---")

    print_command(
        "oci iam user list --compartment-id $TENANCY_ID",
        "List users"
    )

    print_command(
        "oci iam user get --user-id <user-ocid>",
        "Get user details"
    )

    # Groups
    speak_plain("")
    speak_plain("--- Groups ---")

    print_command(
        "oci iam group list --compartment-id $TENANCY_ID",
        "List groups"
    )

    print_command(
        "oci iam group add-user --group-id <group-ocid> --user-id <user-ocid>",
        "Add user to group"
    )

    # Policies
    speak_plain("")
    speak_plain("--- Policies ---")

    print_command(
        "oci iam policy list --compartment-id $COMPARTMENT_ID",
        "List policies in compartment"
    )

    print_command(
        """oci iam policy create \\
    --compartment-id $COMPARTMENT_ID \\
    --name 'my-policy' \\
    --description 'Allow compute access' \\
    --statements '["Allow group Developers to manage instances in compartment DevCompartment"]'""",
        "Create policy"
    )

    # API Keys
    speak_plain("")
    speak_plain("--- API Keys ---")

    print_command(
        "oci iam user api-key list --user-id <user-ocid>",
        "List API keys for user"
    )

    print_command(
        "oci iam user api-key upload --user-id <user-ocid> --key-file ~/.oci/oci_api_key_public.pem",
        "Upload API key"
    )


def db_commands(args):
    """Generate database commands."""
    print_category("Database Commands")

    speak_plain("")
    speak_plain("Common Variables:")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")

    # Autonomous Database
    speak_plain("")
    speak_plain("--- Autonomous Database ---")

    print_command(
        "oci db autonomous-database list --compartment-id $COMPARTMENT_ID",
        "List autonomous databases"
    )

    print_command(
        "oci db autonomous-database get --autonomous-database-id <adb-ocid>",
        "Get autonomous database details"
    )

    print_command(
        """oci db autonomous-database create \\
    --compartment-id $COMPARTMENT_ID \\
    --db-name 'MYDB' \\
    --display-name 'my-adb' \\
    --admin-password 'ComplexPassword123!' \\
    --cpu-core-count 1 \\
    --data-storage-size-in-tbs 1 \\
    --db-workload OLTP \\
    --is-free-tier true""",
        "Create free tier autonomous database"
    )

    print_command(
        "oci db autonomous-database start --autonomous-database-id <adb-ocid>",
        "Start autonomous database"
    )

    print_command(
        "oci db autonomous-database stop --autonomous-database-id <adb-ocid>",
        "Stop autonomous database"
    )

    print_command(
        "oci db autonomous-database generate-wallet --autonomous-database-id <adb-ocid> --password 'WalletPassword123!' --file wallet.zip",
        "Download connection wallet"
    )

    # MySQL
    speak_plain("")
    speak_plain("--- MySQL HeatWave ---")

    print_command(
        "oci mysql db-system list --compartment-id $COMPARTMENT_ID",
        "List MySQL systems"
    )

    print_command(
        """oci mysql db-system create \\
    --compartment-id $COMPARTMENT_ID \\
    --availability-domain $AD \\
    --shape-name 'MySQL.Free' \\
    --subnet-id $SUBNET_ID \\
    --admin-username 'admin' \\
    --admin-password 'ComplexPassword123!' \\
    --data-storage-size-in-gbs 50 \\
    --display-name 'my-mysql'""",
        "Create free tier MySQL"
    )


def container_commands(args):
    """Generate container commands."""
    print_category("Container Commands")

    speak_plain("")
    speak_plain("Common Variables:")
    speak_plain("  export COMPARTMENT_ID='ocid1.compartment.oc1...'")

    # OKE
    speak_plain("")
    speak_plain("--- Kubernetes Engine (OKE) ---")

    print_command(
        "oci ce cluster list --compartment-id $COMPARTMENT_ID",
        "List Kubernetes clusters"
    )

    print_command(
        "oci ce cluster get --cluster-id <cluster-ocid>",
        "Get cluster details"
    )

    print_command(
        "oci ce cluster create-kubeconfig --cluster-id <cluster-ocid> --file ~/.kube/config --token-version 2.0.0",
        "Generate kubeconfig"
    )

    print_command(
        "oci ce node-pool list --compartment-id $COMPARTMENT_ID --cluster-id <cluster-ocid>",
        "List node pools"
    )

    print_command(
        "oci ce node-pool update --node-pool-id <pool-ocid> --size 3",
        "Scale node pool to 3 nodes"
    )

    # Container Instances
    speak_plain("")
    speak_plain("--- Container Instances ---")

    print_command(
        "oci container-instances container-instance list --compartment-id $COMPARTMENT_ID",
        "List container instances"
    )

    print_command(
        "oci container-instances container-instance get --container-instance-id <ci-ocid>",
        "Get container instance details"
    )

    print_command(
        """oci container-instances container-instance create \\
    --compartment-id $COMPARTMENT_ID \\
    --availability-domain $AD \\
    --shape 'CI.Standard.E4.Flex' \\
    --shape-config '{"ocpus": 1, "memoryInGBs": 4}' \\
    --containers '[{
        "displayName": "nginx",
        "imageUrl": "docker.io/nginx:latest"
    }]' \\
    --vnics '[{
        "subnetId": "'$SUBNET_ID'",
        "isPublicIpAssigned": true
    }]' \\
    --display-name 'my-container'""",
        "Create container instance with nginx"
    )

    # Container Registry
    speak_plain("")
    speak_plain("--- Container Registry (OCIR) ---")

    print_command(
        "oci artifacts container repository list --compartment-id $COMPARTMENT_ID",
        "List container repositories"
    )

    print_command(
        "docker login <region>.ocir.io -u '<namespace>/<username>'",
        "Login to OCIR (use auth token as password)"
    )

    print_command(
        "docker tag myimage:latest <region>.ocir.io/<namespace>/myimage:latest",
        "Tag image for OCIR"
    )

    print_command(
        "docker push <region>.ocir.io/<namespace>/myimage:latest",
        "Push image to OCIR"
    )


def interactive_mode(args):
    """Interactive command generator."""
    speak_plain("OCI Command Generator - Interactive Mode")
    speak_plain("=" * 50)
    speak_plain("")
    speak_plain("Select a category:")
    speak_plain("  1. Compute (instances, shapes, images)")
    speak_plain("  2. Network (VCN, subnets, security)")
    speak_plain("  3. Storage (block, object storage)")
    speak_plain("  4. IAM (users, groups, policies)")
    speak_plain("  5. Database (Autonomous DB, MySQL)")
    speak_plain("  6. Containers (OKE, Container Instances)")
    speak_plain("  7. All categories")
    speak_plain("  q. Quit")
    speak_plain("")

    while True:
        choice = input("Enter choice (1-7, or q to quit): ").strip().lower()

        if choice == "q":
            speak("Goodbye!")
            break
        elif choice == "1":
            compute_commands(args)
        elif choice == "2":
            network_commands(args)
        elif choice == "3":
            storage_commands(args)
        elif choice == "4":
            iam_commands(args)
        elif choice == "5":
            db_commands(args)
        elif choice == "6":
            container_commands(args)
        elif choice == "7":
            compute_commands(args)
            network_commands(args)
            storage_commands(args)
            iam_commands(args)
            db_commands(args)
            container_commands(args)
        else:
            speak_plain("Invalid choice. Please enter 1-7 or q.")

        speak_plain("")


def main():
    parser = argparse.ArgumentParser(
        description="OCI Command Generator. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    mkocicmd.py                 # Interactive mode
    mkocicmd.py compute         # Show compute commands
    mkocicmd.py network         # Show network commands
    mkocicmd.py storage         # Show storage commands
    mkocicmd.py iam             # Show IAM commands
    mkocicmd.py db              # Show database commands
    mkocicmd.py container       # Show container commands

Screen Reader Notes:
    Commands are listed with descriptions.
    Each command is on a separate line for easy copying.
    Use Tab to navigate between commands.
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # Interactive (default)
    interactive_parser = subparsers.add_parser("interactive", help="Interactive mode")
    interactive_parser.set_defaults(func=interactive_mode)

    # Compute
    compute_parser = subparsers.add_parser("compute", help="Compute commands")
    compute_parser.set_defaults(func=compute_commands)

    # Network
    network_parser = subparsers.add_parser("network", help="Network commands")
    network_parser.set_defaults(func=network_commands)

    # Storage
    storage_parser = subparsers.add_parser("storage", help="Storage commands")
    storage_parser.set_defaults(func=storage_commands)

    # IAM
    iam_parser = subparsers.add_parser("iam", help="IAM commands")
    iam_parser.set_defaults(func=iam_commands)

    # DB
    db_parser = subparsers.add_parser("db", help="Database commands")
    db_parser.set_defaults(func=db_commands)

    # Container
    container_parser = subparsers.add_parser("container", help="Container commands")
    container_parser.set_defaults(func=container_commands)

    args = parser.parse_args()

    if not args.command:
        interactive_mode(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
