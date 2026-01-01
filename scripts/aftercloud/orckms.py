#!/usr/bin/env python3
"""
Oracle Cloud Vault/KMS Management Tool

Manage Oracle Cloud Infrastructure Vault, Keys, and Secrets.
Designed for accessibility with screen reader friendly output.

Usage:
    orckms.py vaults                       # List vaults
    orckms.py vault <vault-id>             # Show vault details
    orckms.py keys                         # List keys
    orckms.py key <key-id>                 # Show key details
    orckms.py secrets                      # List secrets
    orckms.py secret <secret-id>           # Get secret value
    orckms.py create-secret --name mykey   # Create secret
    orckms.py update-secret <id> <value>   # Update secret
    orckms.py delete-secret <id>           # Delete secret
"""

import argparse
import base64
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


def format_state(state: str) -> str:
    """Format lifecycle state for readability."""
    states = {
        "CREATING": "Creating",
        "ACTIVE": "Active",
        "DELETING": "Deleting",
        "DELETED": "Deleted",
        "SCHEDULING_DELETION": "Scheduled for Deletion",
        "PENDING_DELETION": "Pending Deletion",
        "CANCELLING_DELETION": "Cancelling Deletion",
        "UPDATING": "Updating",
        "BACKUP_IN_PROGRESS": "Backup in Progress",
        "RESTORING": "Restoring",
    }
    return states.get(state, state)


def list_vaults(args):
    """List all vaults."""
    speak("Fetching vaults...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]
    kms_vault_client = oci.key_management.KmsVaultClient(config)

    try:
        response = kms_vault_client.list_vaults(compartment_id=compartment_id)
        vaults = response.data

        if not vaults:
            speak_plain("")
            speak_plain("No vaults found.")
            speak_plain("Create a vault in the Oracle Cloud Console first.")
            return

        speak_plain("")
        speak_plain("Vaults")
        speak_plain("=" * 70)
        speak_plain("")

        for vault in vaults:
            if vault.lifecycle_state == "DELETED":
                continue

            speak_plain(f"  Name: {vault.display_name}")
            speak_plain(f"    ID: {vault.id}")
            speak_plain(f"    State: {format_state(vault.lifecycle_state)}")
            speak_plain(f"    Type: {vault.vault_type}")
            speak_plain(f"    Crypto Endpoint: {vault.crypto_endpoint}")
            speak_plain(f"    Management Endpoint: {vault.management_endpoint}")
            speak_plain(f"    Created: {vault.time_created.strftime('%Y-%m-%d %H:%M')}")
            speak_plain("")

        active_count = len([v for v in vaults if v.lifecycle_state not in ["DELETED", "DELETING"]])
        speak_plain(f"Total: {active_count} vaults")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_vault(args):
    """Show vault details."""
    speak(f"Fetching vault {args.vault_id}...")

    config = get_oci_config(args.profile)
    kms_vault_client = oci.key_management.KmsVaultClient(config)

    try:
        vault = kms_vault_client.get_vault(args.vault_id).data

        speak_plain("")
        speak_plain("Vault Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {vault.display_name}")
        speak_plain(f"  ID: {vault.id}")
        speak_plain(f"  State: {format_state(vault.lifecycle_state)}")
        speak_plain(f"  Type: {vault.vault_type}")
        speak_plain(f"  Compartment ID: {vault.compartment_id}")
        speak_plain("")
        speak_plain("  Endpoints:")
        speak_plain(f"    Crypto Endpoint: {vault.crypto_endpoint}")
        speak_plain(f"    Management Endpoint: {vault.management_endpoint}")
        speak_plain("")
        speak_plain(f"  Created: {vault.time_created.strftime('%Y-%m-%d %H:%M:%S')}")

        if vault.time_of_deletion:
            speak_plain(f"  Scheduled Deletion: {vault.time_of_deletion.strftime('%Y-%m-%d %H:%M:%S')}")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_keys(args):
    """List all keys in a vault."""
    speak("Fetching keys...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]

    # First get vault to get management endpoint
    kms_vault_client = oci.key_management.KmsVaultClient(config)

    try:
        if args.vault:
            # Get specific vault
            vault = kms_vault_client.get_vault(args.vault).data
            vaults = [vault]
        else:
            # List all vaults
            vaults = kms_vault_client.list_vaults(compartment_id=compartment_id).data
            vaults = [v for v in vaults if v.lifecycle_state == "ACTIVE"]

        if not vaults:
            speak_plain("")
            speak_plain("No active vaults found.")
            return

        speak_plain("")
        speak_plain("Encryption Keys")
        speak_plain("=" * 70)
        speak_plain("")

        total_keys = 0

        for vault in vaults:
            speak_plain(f"--- Vault: {vault.display_name} ---")
            speak_plain("")

            # Create KMS management client for this vault
            kms_mgmt_client = oci.key_management.KmsManagementClient(
                config,
                service_endpoint=vault.management_endpoint
            )

            keys = kms_mgmt_client.list_keys(compartment_id=compartment_id).data

            if not keys:
                speak_plain("  No keys in this vault.")
                speak_plain("")
                continue

            for key in keys:
                if key.lifecycle_state == "DELETED":
                    continue

                speak_plain(f"  Name: {key.display_name}")
                speak_plain(f"    ID: {key.id}")
                speak_plain(f"    State: {format_state(key.lifecycle_state)}")
                speak_plain(f"    Algorithm: {key.algorithm}")
                speak_plain(f"    Protection Mode: {key.protection_mode}")
                speak_plain(f"    Created: {key.time_created.strftime('%Y-%m-%d %H:%M')}")
                speak_plain("")
                total_keys += 1

        speak_plain(f"Total: {total_keys} keys across {len(vaults)} vaults")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def show_key(args):
    """Show key details."""
    speak(f"Fetching key {args.key_id}...")

    config = get_oci_config(args.profile)

    # Need to get vault first to find management endpoint
    # Parse key OCID to extract vault region info
    kms_vault_client = oci.key_management.KmsVaultClient(config)
    compartment_id = args.compartment or config["tenancy"]

    try:
        # List vaults to find the one containing this key
        vaults = kms_vault_client.list_vaults(compartment_id=compartment_id).data
        vaults = [v for v in vaults if v.lifecycle_state == "ACTIVE"]

        key_found = False
        for vault in vaults:
            try:
                kms_mgmt_client = oci.key_management.KmsManagementClient(
                    config,
                    service_endpoint=vault.management_endpoint
                )
                key = kms_mgmt_client.get_key(args.key_id).data
                key_found = True

                speak_plain("")
                speak_plain("Encryption Key Details")
                speak_plain("=" * 70)
                speak_plain("")
                speak_plain(f"  Name: {key.display_name}")
                speak_plain(f"  ID: {key.id}")
                speak_plain(f"  State: {format_state(key.lifecycle_state)}")
                speak_plain(f"  Vault: {vault.display_name}")
                speak_plain(f"  Compartment ID: {key.compartment_id}")
                speak_plain("")
                speak_plain("  Key Configuration:")
                speak_plain(f"    Algorithm: {key.key_shape.algorithm}")
                speak_plain(f"    Length: {key.key_shape.length} bits")
                speak_plain(f"    Protection Mode: {key.protection_mode}")
                speak_plain(f"    Current Version: {key.current_key_version}")
                speak_plain("")
                speak_plain(f"  Created: {key.time_created.strftime('%Y-%m-%d %H:%M:%S')}")

                if key.time_of_deletion:
                    speak_plain(f"  Scheduled Deletion: {key.time_of_deletion.strftime('%Y-%m-%d %H:%M:%S')}")

                speak_plain("")
                break

            except oci.exceptions.ServiceError:
                continue

        if not key_found:
            print(f"Error: Key {args.key_id} not found in any vault")
            sys.exit(1)

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def list_secrets(args):
    """List all secrets."""
    speak("Fetching secrets...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]
    vaults_client = oci.vault.VaultsClient(config)

    try:
        response = vaults_client.list_secrets(compartment_id=compartment_id)
        secrets = response.data

        if not secrets:
            speak_plain("")
            speak_plain("No secrets found.")
            speak_plain("Use 'orckms.py create-secret' to create one.")
            return

        speak_plain("")
        speak_plain("Secrets")
        speak_plain("=" * 70)
        speak_plain("")

        for secret in secrets:
            if secret.lifecycle_state == "DELETED":
                continue

            speak_plain(f"  Name: {secret.secret_name}")
            speak_plain(f"    ID: {secret.id}")
            speak_plain(f"    State: {format_state(secret.lifecycle_state)}")
            speak_plain(f"    Created: {secret.time_created.strftime('%Y-%m-%d %H:%M')}")
            if secret.description:
                speak_plain(f"    Description: {secret.description}")
            speak_plain("")

        active_count = len([s for s in secrets if s.lifecycle_state not in ["DELETED", "DELETING"]])
        speak_plain(f"Total: {active_count} secrets")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def get_secret(args):
    """Get secret value."""
    speak(f"Fetching secret {args.secret_id}...")

    config = get_oci_config(args.profile)
    secrets_client = oci.secrets.SecretsClient(config)
    vaults_client = oci.vault.VaultsClient(config)

    try:
        # Get secret metadata
        secret_metadata = vaults_client.get_secret(args.secret_id).data

        speak_plain("")
        speak_plain("Secret Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  Name: {secret_metadata.secret_name}")
        speak_plain(f"  ID: {secret_metadata.id}")
        speak_plain(f"  State: {format_state(secret_metadata.lifecycle_state)}")
        if secret_metadata.description:
            speak_plain(f"  Description: {secret_metadata.description}")
        speak_plain(f"  Created: {secret_metadata.time_created.strftime('%Y-%m-%d %H:%M:%S')}")

        # Get secret value
        if not args.show_value:
            speak_plain("")
            speak_plain("  Value: [hidden, use --show-value to display]")
        else:
            speak_plain("")
            speak("Retrieving secret value...")

            response = secrets_client.get_secret_bundle(
                secret_id=args.secret_id,
                stage="CURRENT"
            )
            bundle = response.data

            if bundle.secret_bundle_content:
                content_type = bundle.secret_bundle_content.content_type
                if content_type == "BASE64":
                    value = base64.b64decode(bundle.secret_bundle_content.content).decode('utf-8')
                else:
                    value = bundle.secret_bundle_content.content

                speak_plain(f"  Value: {value}")

        speak_plain("")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def create_secret(args):
    """Create a new secret."""
    speak("Creating secret...")

    config = get_oci_config(args.profile)
    compartment_id = args.compartment or config["tenancy"]
    vaults_client = oci.vault.VaultsClient(config)

    try:
        # Get the secret value
        if args.value:
            secret_value = args.value
        elif args.value_file:
            with open(Path(args.value_file).expanduser()) as f:
                secret_value = f.read()
        else:
            print("Error: Either --value or --value-file is required")
            sys.exit(1)

        # Base64 encode the value
        encoded_value = base64.b64encode(secret_value.encode('utf-8')).decode('utf-8')

        secret_content = oci.vault.models.Base64SecretContentDetails(
            content_type="BASE64",
            content=encoded_value
        )

        create_details = oci.vault.models.CreateSecretDetails(
            compartment_id=compartment_id,
            vault_id=args.vault,
            key_id=args.key,
            secret_name=args.name,
            description=args.description,
            secret_content=secret_content,
            freeform_tags={"ManagedBy": "orckms"}
        )

        response = vaults_client.create_secret(create_details)
        secret = response.data

        speak("Secret created successfully!")
        speak_plain("")
        speak_plain(f"  Secret ID: {secret.id}")
        speak_plain(f"  Name: {secret.secret_name}")
        speak_plain(f"  State: {format_state(secret.lifecycle_state)}")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def update_secret(args):
    """Update a secret value."""
    speak(f"Updating secret {args.secret_id}...")

    config = get_oci_config(args.profile)
    vaults_client = oci.vault.VaultsClient(config)

    try:
        # Get the new value
        if args.value:
            secret_value = args.value
        elif args.value_file:
            with open(Path(args.value_file).expanduser()) as f:
                secret_value = f.read()
        else:
            print("Error: Either --value or --value-file is required")
            sys.exit(1)

        # Base64 encode the value
        encoded_value = base64.b64encode(secret_value.encode('utf-8')).decode('utf-8')

        secret_content = oci.vault.models.Base64SecretContentDetails(
            content_type="BASE64",
            content=encoded_value
        )

        update_details = oci.vault.models.UpdateSecretDetails(
            secret_content=secret_content
        )

        response = vaults_client.update_secret(args.secret_id, update_details)
        secret = response.data

        speak("Secret updated successfully!")
        speak_plain("")
        speak_plain(f"  Secret ID: {secret.id}")
        speak_plain(f"  Name: {secret.secret_name}")
        speak_plain(f"  State: {format_state(secret.lifecycle_state)}")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def delete_secret(args):
    """Delete (schedule deletion of) a secret."""
    speak(f"Scheduling deletion of secret {args.secret_id}...")
    speak("WARNING: This will schedule the secret for permanent deletion!")

    if not args.yes:
        confirm = input("Type 'yes' to confirm deletion: ")
        if confirm.lower() != "yes":
            speak("Deletion cancelled.")
            return

    config = get_oci_config(args.profile)
    vaults_client = oci.vault.VaultsClient(config)

    try:
        # Schedule deletion (minimum 1 day, maximum 30 days)
        from datetime import timedelta
        deletion_time = datetime.utcnow() + timedelta(days=args.days or 7)

        schedule_details = oci.vault.models.ScheduleSecretDeletionDetails(
            time_of_deletion=deletion_time
        )

        vaults_client.schedule_secret_deletion(args.secret_id, schedule_details)

        speak(f"Secret scheduled for deletion on {deletion_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        speak("You can cancel this with 'oci vault secret cancel-secret-deletion'")

    except oci.exceptions.ServiceError as e:
        print(f"Error: {e.message}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Cloud Vault/KMS Management Tool. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    orckms.py vaults                        # List all vaults
    orckms.py vault ocid1.vault...          # Show vault details
    orckms.py keys                          # List all keys
    orckms.py keys --vault ocid1.vault...   # List keys in vault
    orckms.py secrets                       # List all secrets
    orckms.py secret ocid1.secret...        # Show secret metadata
    orckms.py secret <id> --show-value      # Show secret value

    orckms.py create-secret --name mykey \\
        --vault ocid1.vault... \\
        --key ocid1.key... \\
        --value "my-secret-value"

    orckms.py update-secret ocid1.secret... --value "new-value"
    orckms.py delete-secret ocid1.secret...

Screen Reader Notes:
    All output is plain text with clear labels.
    Secret values are hidden by default for security.
    Use --show-value flag to display secret contents.
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

    # vaults
    vaults_parser = subparsers.add_parser("vaults", help="List vaults")
    vaults_parser.set_defaults(func=list_vaults)

    # vault
    vault_parser = subparsers.add_parser("vault", help="Show vault details")
    vault_parser.add_argument("vault_id", help="Vault OCID")
    vault_parser.set_defaults(func=show_vault)

    # keys
    keys_parser = subparsers.add_parser("keys", help="List keys")
    keys_parser.add_argument("--vault", help="Vault OCID (optional)")
    keys_parser.set_defaults(func=list_keys)

    # key
    key_parser = subparsers.add_parser("key", help="Show key details")
    key_parser.add_argument("key_id", help="Key OCID")
    key_parser.set_defaults(func=show_key)

    # secrets
    secrets_parser = subparsers.add_parser("secrets", help="List secrets")
    secrets_parser.set_defaults(func=list_secrets)

    # secret
    secret_parser = subparsers.add_parser("secret", help="Get secret")
    secret_parser.add_argument("secret_id", help="Secret OCID")
    secret_parser.add_argument("--show-value", action="store_true", help="Display secret value")
    secret_parser.set_defaults(func=get_secret)

    # create-secret
    create_parser = subparsers.add_parser("create-secret", help="Create secret")
    create_parser.add_argument("--name", required=True, help="Secret name")
    create_parser.add_argument("--vault", required=True, help="Vault OCID")
    create_parser.add_argument("--key", required=True, help="Encryption key OCID")
    create_parser.add_argument("--value", help="Secret value")
    create_parser.add_argument("--value-file", help="Read value from file")
    create_parser.add_argument("--description", help="Secret description")
    create_parser.set_defaults(func=create_secret)

    # update-secret
    update_parser = subparsers.add_parser("update-secret", help="Update secret")
    update_parser.add_argument("secret_id", help="Secret OCID")
    update_parser.add_argument("--value", help="New secret value")
    update_parser.add_argument("--value-file", help="Read value from file")
    update_parser.set_defaults(func=update_secret)

    # delete-secret
    delete_parser = subparsers.add_parser("delete-secret", help="Delete secret")
    delete_parser.add_argument("secret_id", help="Secret OCID")
    delete_parser.add_argument("--days", type=int, default=7, help="Days until deletion (1-30)")
    delete_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    delete_parser.set_defaults(func=delete_secret)

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
