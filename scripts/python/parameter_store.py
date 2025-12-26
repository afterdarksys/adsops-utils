#!/usr/bin/env python3
"""
parameter_store.py - OCI Vault Secrets Management
After Dark Systems - Ops Utils

This module provides functions for managing secrets in OCI Vault
including creation, retrieval, rotation, and versioning.
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from common import (
    check_dependencies, confirm_action, log_error, log_info, log_success,
    log_warn, run_oci_command
)


# Configuration from environment
OCI_PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID", "")
VAULT_OCID = os.environ.get("VAULT_OCID", "")
KEY_OCID = os.environ.get("KEY_OCID", "")


def list_vaults(compartment: Optional[str] = None) -> None:
    """List vaults in compartment."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing vaults...")
    result = run_oci_command([
        "kms", "management", "vault", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for vault in result["data"]:
            print(f"{vault['id']}\t{vault['display-name']}\t{vault['vault-type']}\t{vault['lifecycle-state']}")


def get_vault(vault_id: Optional[str] = None) -> None:
    """Get vault details."""
    vault_id = vault_id or VAULT_OCID
    if not vault_id:
        log_error("Vault OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "kms", "management", "vault", "get",
        "--vault-id", vault_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        data = result["data"]
        output = {
            "id": data.get("id"),
            "displayName": data.get("display-name"),
            "vaultType": data.get("vault-type"),
            "cryptoEndpoint": data.get("crypto-endpoint"),
            "managementEndpoint": data.get("management-endpoint"),
            "state": data.get("lifecycle-state")
        }
        print(json.dumps(output, indent=2))


def list_keys(compartment: Optional[str] = None, vault_id: Optional[str] = None) -> None:
    """List keys in vault."""
    compartment = compartment or COMPARTMENT_OCID
    vault_id = vault_id or VAULT_OCID

    if not compartment or not vault_id:
        log_error("Compartment OCID and Vault OCID required.")
        sys.exit(1)

    # Get management endpoint
    vault_result = run_oci_command([
        "kms", "management", "vault", "get",
        "--vault-id", vault_id
    ], profile=OCI_PROFILE)

    if not vault_result or "data" not in vault_result:
        log_error("Failed to get vault details")
        sys.exit(1)

    mgmt_endpoint = vault_result["data"]["management-endpoint"]

    log_info("Listing keys...")
    result = run_oci_command([
        "kms", "management", "key", "list",
        "--compartment-id", compartment,
        "--endpoint", mgmt_endpoint,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for key in result["data"]:
            print(f"{key['id']}\t{key['display-name']}\t{key['algorithm']}\t{key['lifecycle-state']}")


def list_secrets(compartment: Optional[str] = None, vault_id: Optional[str] = None) -> None:
    """List secrets in vault."""
    compartment = compartment or COMPARTMENT_OCID

    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing secrets...")

    cmd = ["vault", "secret", "list", "--compartment-id", compartment, "--all"]
    if vault_id or VAULT_OCID:
        cmd.extend(["--vault-id", vault_id or VAULT_OCID])

    result = run_oci_command(cmd, profile=OCI_PROFILE)

    if result and "data" in result:
        for secret in result["data"]:
            print(f"{secret['id']}\t{secret['secret-name']}\t{secret['lifecycle-state']}")


def get_secret_metadata(secret_id: str) -> None:
    """Get secret metadata."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "vault", "secret", "get",
        "--secret-id", secret_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        data = result["data"]
        output = {
            "id": data.get("id"),
            "secretName": data.get("secret-name"),
            "currentVersionNumber": data.get("current-version-number"),
            "state": data.get("lifecycle-state"),
            "vaultId": data.get("vault-id"),
            "keyId": data.get("key-id")
        }
        print(json.dumps(output, indent=2))


def get_secret(secret_id: str) -> None:
    """Get secret value (current version)."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "secrets", "secret-bundle", "get",
        "--secret-id", secret_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        content = result["data"].get("secret-bundle-content", {})
        encoded = content.get("content", "")
        if encoded:
            decoded = base64.b64decode(encoded).decode('utf-8')
            print(decoded)


def get_secret_version(secret_id: str, version: Optional[str] = None) -> None:
    """Get secret value by version."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    cmd = ["secrets", "secret-bundle", "get", "--secret-id", secret_id]
    if version:
        cmd.extend(["--version-number", version])

    result = run_oci_command(cmd, profile=OCI_PROFILE)

    if result and "data" in result:
        content = result["data"].get("secret-bundle-content", {})
        encoded = content.get("content", "")
        if encoded:
            decoded = base64.b64decode(encoded).decode('utf-8')
            print(decoded)


def create_secret(
    compartment: str,
    vault_id: str,
    key_id: str,
    name: str,
    value: str,
    description: str = ""
) -> None:
    """Create new secret."""
    compartment = compartment or COMPARTMENT_OCID
    vault_id = vault_id or VAULT_OCID
    key_id = key_id or KEY_OCID

    if not all([compartment, vault_id, key_id, name, value]):
        log_error("Usage: create <compartment> <vault_id> <key_id> <name> <value> [description]")
        sys.exit(1)

    encoded_value = base64.b64encode(value.encode('utf-8')).decode('utf-8')

    log_info(f"Creating secret: {name}")

    cmd = [
        "vault", "secret", "create-base64",
        "--compartment-id", compartment,
        "--vault-id", vault_id,
        "--key-id", key_id,
        "--secret-name", name,
        "--secret-content-content", encoded_value
    ]

    if description:
        cmd.extend(["--description", description])

    result = run_oci_command(cmd, profile=OCI_PROFILE)

    if result and "data" in result:
        output = {
            "id": result["data"]["id"],
            "name": result["data"]["secret-name"]
        }
        print(json.dumps(output, indent=2))
    log_success(f"Secret created: {name}")


def update_secret(secret_id: str, value: str) -> None:
    """Update secret (create new version)."""
    if not secret_id or not value:
        log_error("Usage: update <secret_id> <value>")
        sys.exit(1)

    encoded_value = base64.b64encode(value.encode('utf-8')).decode('utf-8')

    log_info("Updating secret...")

    result = run_oci_command([
        "vault", "secret", "update-base64",
        "--secret-id", secret_id,
        "--secret-content-content", encoded_value
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        output = {
            "id": result["data"]["id"],
            "name": result["data"]["secret-name"]
        }
        print(json.dumps(output, indent=2))
    log_success("Secret updated")


def delete_secret(secret_id: str, days: int = 30) -> None:
    """Schedule secret for deletion."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    log_warn(f"Scheduling secret for deletion in {days} days")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    deletion_time = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    run_oci_command([
        "vault", "secret", "schedule-secret-deletion",
        "--secret-id", secret_id,
        "--time-of-deletion", deletion_time
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Secret scheduled for deletion")


def cancel_deletion(secret_id: str) -> None:
    """Cancel pending secret deletion."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    run_oci_command([
        "vault", "secret", "cancel-secret-deletion",
        "--secret-id", secret_id
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Secret deletion cancelled")


def list_versions(secret_id: str) -> None:
    """List secret versions."""
    if not secret_id:
        log_error("Secret OCID required.")
        sys.exit(1)

    log_info("Listing secret versions...")
    result = run_oci_command([
        "vault", "secret-version", "list",
        "--secret-id", secret_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for version in result["data"]:
            stages = ", ".join(version.get("stages", []))
            print(f"{version['version-number']}\t{stages}\t{version['time-created']}")


def rotate_secret(secret_id: str, new_value: str) -> None:
    """Rotate secret (create new version)."""
    if not secret_id or not new_value:
        log_error("Usage: rotate <secret_id> <new_value>")
        sys.exit(1)

    log_info("Rotating secret...")

    # Get current version
    result = run_oci_command([
        "vault", "secret", "get",
        "--secret-id", secret_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        current_version = result["data"].get("current-version-number")

        # Create new version
        update_secret(secret_id, new_value)

        log_success(f"Secret rotated. Previous version: {current_version}")


def export_metadata(compartment: Optional[str] = None, output_file: str = "secrets-metadata.json") -> None:
    """Export secrets metadata to JSON file."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Exporting secrets metadata...")

    result = run_oci_command([
        "vault", "secret", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        metadata = [
            {
                "id": s["id"],
                "name": s["secret-name"],
                "state": s["lifecycle-state"],
                "vaultId": s["vault-id"]
            }
            for s in result["data"]
        ]

        with open(output_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        log_success(f"Metadata exported to: {output_file}")


def main():
    """Main entry point."""
    if not check_dependencies(["oci"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI Vault Secrets Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list-vaults [compartment]                        List vaults
  get-vault [vault_id]                             Get vault details
  list-keys [compartment] [vault_id]               List keys
  list [compartment] [vault_id]                    List secrets
  get-metadata <secret_id>                         Get secret metadata
  get <secret_id>                                  Get secret value
  get-version <secret_id> [version]                Get specific version
  create <comp> <vault> <key> <name> <value> [desc]
                                                   Create secret
  update <secret_id> <value>                       Update secret
  delete <secret_id> [days]                        Schedule deletion
  cancel-deletion <secret_id>                      Cancel deletion
  list-versions <secret_id>                        List versions
  rotate <secret_id> <new_value>                   Rotate secret
  export-metadata [compartment] [file]             Export metadata

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
  VAULT_OCID        Default vault OCID
  KEY_OCID          Default encryption key OCID
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        "list-vaults": lambda a: list_vaults(a[0] if a else None),
        "get-vault": lambda a: get_vault(a[0] if a else None),
        "list-keys": lambda a: list_keys(
            a[0] if a else None,
            a[1] if len(a) > 1 else None
        ),
        "list": lambda a: list_secrets(
            a[0] if a else None,
            a[1] if len(a) > 1 else None
        ),
        "get-metadata": lambda a: get_secret_metadata(a[0]),
        "get": lambda a: get_secret(a[0]),
        "get-version": lambda a: get_secret_version(a[0], a[1] if len(a) > 1 else None),
        "create": lambda a: create_secret(
            a[0], a[1], a[2], a[3], a[4],
            a[5] if len(a) > 5 else ""
        ),
        "update": lambda a: update_secret(a[0], a[1]),
        "delete": lambda a: delete_secret(a[0], int(a[1]) if len(a) > 1 else 30),
        "cancel-deletion": lambda a: cancel_deletion(a[0]),
        "list-versions": lambda a: list_versions(a[0]),
        "rotate": lambda a: rotate_secret(a[0], a[1]),
        "export-metadata": lambda a: export_metadata(
            a[0] if a else None,
            a[1] if len(a) > 1 else "secrets-metadata.json"
        ),
    }

    if args.command in commands:
        try:
            commands[args.command](args.args)
        except IndexError:
            log_error(f"Missing required arguments for {args.command}")
            parser.print_help()
            sys.exit(1)
    else:
        log_error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
