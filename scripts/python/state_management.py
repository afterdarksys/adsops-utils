#!/usr/bin/env python3
"""
state_management.py - OCI Object Storage State Management for Terraform
After Dark Systems - Ops Utils

This module provides functions for managing Terraform state
stored in OCI Object Storage, including locking and versioning.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Optional

from common import (
    check_dependencies, confirm_action, log_error, log_info, log_success,
    log_warn, run_oci_command
)


# Configuration from environment
OCI_PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
NAMESPACE = os.environ.get("NAMESPACE", "")
STATE_BUCKET = os.environ.get("STATE_BUCKET", "terraform-state")
LOCK_BUCKET = os.environ.get("LOCK_BUCKET", "terraform-locks")
COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID", "")


def get_namespace() -> str:
    """Get OCI namespace if not set."""
    global NAMESPACE
    if not NAMESPACE:
        result = run_oci_command([
            "os", "ns", "get"
        ], profile=OCI_PROFILE)
        if result and "data" in result:
            NAMESPACE = result["data"]
    return NAMESPACE


def list_states(bucket: Optional[str] = None, prefix: str = "") -> None:
    """List state files in bucket."""
    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    log_info(f"Listing state files in {ns}/{bucket}/{prefix}")

    result = run_oci_command([
        "os", "object", "list",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--prefix", prefix,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for obj in result["data"]:
            if obj["name"].endswith(".tfstate"):
                print(f"{obj['name']}\t{obj['size']}\t{obj['time-modified']}")


def get_state(key: str, output_file: Optional[str] = None, bucket: Optional[str] = None) -> None:
    """Get state file content."""
    if not key:
        log_error("Usage: get <key> [output_file] [bucket]")
        sys.exit(1)

    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    cmd = [
        "oci", "os", "object", "get",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--name", key,
        "--profile", OCI_PROFILE
    ]

    if output_file:
        cmd.extend(["--file", output_file])
        subprocess.run(cmd, check=True)
        log_success(f"State downloaded to: {output_file}")
    else:
        cmd.extend(["--file", "/dev/stdout"])
        subprocess.run(cmd, check=True)


def put_state(key: str, file_path: str, bucket: Optional[str] = None) -> None:
    """Upload state file."""
    if not key or not file_path:
        log_error("Usage: put <key> <file> [bucket]")
        sys.exit(1)

    if not os.path.exists(file_path):
        log_error(f"File not found: {file_path}")
        sys.exit(1)

    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    log_warn(f"Uploading state to {ns}/{bucket}/{key}")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    subprocess.run([
        "oci", "os", "object", "put",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--name", key,
        "--file", file_path,
        "--profile", OCI_PROFILE,
        "--force"
    ], check=True)

    log_success("State uploaded")


def delete_state(key: str, bucket: Optional[str] = None) -> None:
    """Delete state file."""
    if not key:
        log_error("Usage: delete <key> [bucket]")
        sys.exit(1)

    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    log_warn(f"Deleting state: {ns}/{bucket}/{key}")
    if not confirm_action("This is permanent! Continue?"):
        log_info("Cancelled.")
        return

    subprocess.run([
        "oci", "os", "object", "delete",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--name", key,
        "--profile", OCI_PROFILE,
        "--force"
    ], check=True)

    log_success("State deleted")


def list_versions(key: str, bucket: Optional[str] = None) -> None:
    """List state versions."""
    if not key:
        log_error("Usage: list-versions <key> [bucket]")
        sys.exit(1)

    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    log_info(f"Listing versions for: {ns}/{bucket}/{key}")

    result = run_oci_command([
        "os", "object-version", "list",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--prefix", key,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for version in result["data"]:
            print(f"{version['version-id']}\t{version['size']}\t{version['time-modified']}")


def restore_version(key: str, version_id: str, bucket: Optional[str] = None) -> None:
    """Restore state from version."""
    if not key or not version_id:
        log_error("Usage: restore <key> <version_id> [bucket]")
        sys.exit(1)

    bucket = bucket or STATE_BUCKET
    ns = get_namespace()

    log_warn(f"Restoring {ns}/{bucket}/{key} from version {version_id}")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    # Download version to temp file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_file = tmp.name

    try:
        subprocess.run([
            "oci", "os", "object", "get",
            "--namespace-name", ns,
            "--bucket-name", bucket,
            "--name", key,
            "--version-id", version_id,
            "--file", temp_file,
            "--profile", OCI_PROFILE
        ], check=True)

        # Upload as current version
        subprocess.run([
            "oci", "os", "object", "put",
            "--namespace-name", ns,
            "--bucket-name", bucket,
            "--name", key,
            "--file", temp_file,
            "--profile", OCI_PROFILE,
            "--force"
        ], check=True)

        log_success(f"State restored from version: {version_id}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def list_locks(bucket: Optional[str] = None) -> None:
    """List state locks."""
    bucket = bucket or LOCK_BUCKET
    ns = get_namespace()

    log_info(f"Listing state locks in {ns}/{bucket}")

    result = run_oci_command([
        "os", "object", "list",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for obj in result["data"]:
            if obj["name"].endswith(".lock"):
                print(f"{obj['name']}\t{obj['size']}\t{obj['time-modified']}")


def check_lock(state_key: str, bucket: Optional[str] = None) -> bool:
    """Check if state is locked."""
    if not state_key:
        log_error("State key required.")
        sys.exit(1)

    bucket = bucket or LOCK_BUCKET
    ns = get_namespace()
    lock_key = f"{state_key}.lock"

    try:
        subprocess.run([
            "oci", "os", "object", "head",
            "--namespace-name", ns,
            "--bucket-name", bucket,
            "--name", lock_key,
            "--profile", OCI_PROFILE
        ], check=True, capture_output=True)

        log_warn("State is LOCKED")
        # Get lock content
        result = subprocess.run([
            "oci", "os", "object", "get",
            "--namespace-name", ns,
            "--bucket-name", bucket,
            "--name", lock_key,
            "--file", "/dev/stdout",
            "--profile", OCI_PROFILE
        ], capture_output=True, text=True)
        if result.stdout:
            print(json.dumps(json.loads(result.stdout), indent=2))
        return False
    except subprocess.CalledProcessError:
        log_success("State is unlocked")
        return True


def force_unlock(state_key: str, bucket: Optional[str] = None) -> None:
    """Force unlock state."""
    if not state_key:
        log_error("State key required.")
        sys.exit(1)

    bucket = bucket or LOCK_BUCKET
    ns = get_namespace()
    lock_key = f"{state_key}.lock"

    log_warn(f"Force unlocking: {lock_key}")
    if not confirm_action("This is dangerous! Continue?"):
        log_info("Cancelled.")
        return

    subprocess.run([
        "oci", "os", "object", "delete",
        "--namespace-name", ns,
        "--bucket-name", bucket,
        "--name", lock_key,
        "--profile", OCI_PROFILE,
        "--force"
    ], check=True)

    log_success("Lock removed")


# Terraform State Operations
def tf_state_list() -> None:
    """List resources in Terraform state."""
    subprocess.run(["terraform", "state", "list"], check=True)


def tf_state_show(resource: str) -> None:
    """Show resource in Terraform state."""
    if not resource:
        log_error("Resource address required.")
        sys.exit(1)
    subprocess.run(["terraform", "state", "show", resource], check=True)


def tf_state_mv(source: str, destination: str) -> None:
    """Move resource in state."""
    if not source or not destination:
        log_error("Usage: tf-mv <source> <destination>")
        sys.exit(1)

    log_warn(f"Moving state: {source} -> {destination}")
    subprocess.run(["terraform", "state", "mv", source, destination], check=True)
    log_success("State moved")


def tf_state_rm(resource: str) -> None:
    """Remove resource from state."""
    if not resource:
        log_error("Resource address required.")
        sys.exit(1)

    log_warn(f"Removing from state: {resource}")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    subprocess.run(["terraform", "state", "rm", resource], check=True)
    log_success("Resource removed from state")


def tf_state_import(resource: str, resource_id: str) -> None:
    """Import resource into state."""
    if not resource or not resource_id:
        log_error("Usage: tf-import <resource_address> <resource_id>")
        sys.exit(1)

    log_info(f"Importing: {resource} = {resource_id}")
    subprocess.run(["terraform", "import", resource, resource_id], check=True)
    log_success("Resource imported")


def tf_state_pull(output_file: str = "terraform.tfstate.backup") -> None:
    """Pull remote state to local."""
    with open(output_file, 'w') as f:
        subprocess.run(["terraform", "state", "pull"], stdout=f, check=True)
    log_success(f"State pulled to: {output_file}")


def tf_state_push(file_path: str = "terraform.tfstate") -> None:
    """Push local state to remote."""
    if not os.path.exists(file_path):
        log_error(f"State file not found: {file_path}")
        sys.exit(1)

    log_warn(f"Pushing state from: {file_path}")
    if not confirm_action("This is dangerous! Continue?"):
        log_info("Cancelled.")
        return

    subprocess.run(["terraform", "state", "push", file_path], check=True)
    log_success("State pushed")


def tf_refresh() -> None:
    """Refresh Terraform state."""
    log_info("Refreshing state...")
    subprocess.run(["terraform", "refresh"], check=True)
    log_success("State refreshed")


def create_state_bucket(bucket: Optional[str] = None, compartment: Optional[str] = None) -> None:
    """Create state bucket with versioning."""
    bucket = bucket or STATE_BUCKET
    compartment = compartment or COMPARTMENT_OCID

    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    ns = get_namespace()

    log_info(f"Creating state bucket: {ns}/{bucket}")

    result = run_oci_command([
        "os", "bucket", "create",
        "--namespace-name", ns,
        "--compartment-id", compartment,
        "--name", bucket,
        "--versioning", "Enabled"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        output = {
            "name": result["data"]["name"],
            "namespace": result["data"]["namespace"],
            "versioning": result["data"]["versioning"]
        }
        print(json.dumps(output, indent=2))

    log_success("Bucket created with versioning enabled")


def create_lock_bucket(bucket: Optional[str] = None, compartment: Optional[str] = None) -> None:
    """Create lock bucket."""
    bucket = bucket or LOCK_BUCKET
    compartment = compartment or COMPARTMENT_OCID

    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    ns = get_namespace()

    log_info(f"Creating lock bucket: {ns}/{bucket}")

    result = run_oci_command([
        "os", "bucket", "create",
        "--namespace-name", ns,
        "--compartment-id", compartment,
        "--name", bucket
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        output = {
            "name": result["data"]["name"],
            "namespace": result["data"]["namespace"]
        }
        print(json.dumps(output, indent=2))

    log_success("Lock bucket created")


def main():
    """Main entry point."""
    if not check_dependencies(["oci", "terraform"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI Object Storage State Management for Terraform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list [bucket] [prefix]                     List state files
  get <key> [output_file] [bucket]           Download state
  put <key> <file> [bucket]                  Upload state
  delete <key> [bucket]                      Delete state
  list-versions <key> [bucket]               List versions
  restore <key> <version_id> [bucket]        Restore from version

  list-locks [bucket]                        List locks
  check-lock <state_key> [bucket]            Check if locked
  force-unlock <state_key> [bucket]          Force unlock

  tf-list                                    Terraform state list
  tf-show <resource>                         Terraform state show
  tf-mv <source> <destination>               Terraform state mv
  tf-rm <resource>                           Terraform state rm
  tf-import <resource> <id>                  Terraform import
  tf-pull [output_file]                      Pull remote state
  tf-push [state_file]                       Push local state
  tf-refresh                                 Refresh state

  create-bucket [bucket] [compartment]       Create state bucket
  create-lock-bucket [bucket] [compartment]  Create lock bucket

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  NAMESPACE         OCI namespace (auto-detected)
  STATE_BUCKET      State bucket name (default: terraform-state)
  LOCK_BUCKET       Lock bucket name (default: terraform-locks)
  COMPARTMENT_OCID  Default compartment OCID
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        "list": lambda a: list_states(a[0] if a else None, a[1] if len(a) > 1 else ""),
        "get": lambda a: get_state(a[0], a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None),
        "put": lambda a: put_state(a[0], a[1], a[2] if len(a) > 2 else None),
        "delete": lambda a: delete_state(a[0], a[1] if len(a) > 1 else None),
        "list-versions": lambda a: list_versions(a[0], a[1] if len(a) > 1 else None),
        "restore": lambda a: restore_version(a[0], a[1], a[2] if len(a) > 2 else None),
        "list-locks": lambda a: list_locks(a[0] if a else None),
        "check-lock": lambda a: check_lock(a[0], a[1] if len(a) > 1 else None),
        "force-unlock": lambda a: force_unlock(a[0], a[1] if len(a) > 1 else None),
        "tf-list": lambda a: tf_state_list(),
        "tf-show": lambda a: tf_state_show(a[0]),
        "tf-mv": lambda a: tf_state_mv(a[0], a[1]),
        "tf-rm": lambda a: tf_state_rm(a[0]),
        "tf-import": lambda a: tf_state_import(a[0], a[1]),
        "tf-pull": lambda a: tf_state_pull(a[0] if a else "terraform.tfstate.backup"),
        "tf-push": lambda a: tf_state_push(a[0] if a else "terraform.tfstate"),
        "tf-refresh": lambda a: tf_refresh(),
        "create-bucket": lambda a: create_state_bucket(a[0] if a else None, a[1] if len(a) > 1 else None),
        "create-lock-bucket": lambda a: create_lock_bucket(a[0] if a else None, a[1] if len(a) > 1 else None),
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
