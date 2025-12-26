#!/usr/bin/env python3
"""
patch_management.py - OCI OS Management Patch Operations
After Dark Systems - Ops Utils

This module provides functions for managing patches and updates
on OCI managed instances.
"""

import argparse
import json
import os
import sys
from typing import Optional

from common import (
    check_dependencies, confirm_action, log_error, log_info, log_success,
    log_warn, run_oci_command
)


# Configuration from environment
OCI_PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID", "")


def list_managed_instances(compartment: Optional[str] = None) -> None:
    """List managed instances in compartment."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing managed instances...")
    result = run_oci_command([
        "os-management", "managed-instance", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for instance in result["data"]:
            updates = instance.get("updates-available", 0)
            security = instance.get("security-updates-available", 0)
            print(f"{instance['id']}\t{instance['display-name']}\t{instance['status']}\t{updates} updates\t{security} security")


def list_available_updates(instance_id: str) -> None:
    """List available updates for an instance."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_info("Listing available updates...")
    result = run_oci_command([
        "os-management", "managed-instance", "list-available-updates",
        "--managed-instance-id", instance_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for update in result["data"]:
            print(f"{update['display-name']}\t{update['type']}\t{update['update-type']}")


def list_security_updates(instance_id: str) -> None:
    """List security updates for an instance."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_info("Listing security updates...")
    result = run_oci_command([
        "os-management", "managed-instance", "list-available-updates",
        "--managed-instance-id", instance_id,
        "--update-type", "SECURITY",
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for update in result["data"]:
            print(f"{update['display-name']}\t{update['type']}\t{update.get('related-cves', [])}")


def install_all_updates(instance_id: str) -> None:
    """Install all available updates on an instance."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_warn("Installing ALL updates on instance...")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    result = run_oci_command([
        "os-management", "managed-instance", "install-all-updates",
        "--managed-instance-id", instance_id,
        "--update-type", "ALL"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))
    log_success("Update installation initiated")


def install_security_updates(instance_id: str) -> None:
    """Install security updates only."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_warn("Installing SECURITY updates on instance...")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    result = run_oci_command([
        "os-management", "managed-instance", "install-all-updates",
        "--managed-instance-id", instance_id,
        "--update-type", "SECURITY"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))
    log_success("Security update installation initiated")


def install_package_update(instance_id: str, package_name: str) -> None:
    """Install a specific package update."""
    if not instance_id or not package_name:
        log_error("Usage: install-package <instance_id> <package_name>")
        sys.exit(1)

    log_info(f"Installing package update: {package_name}")

    result = run_oci_command([
        "os-management", "managed-instance", "install-package-update",
        "--managed-instance-id", instance_id,
        "--software-package-name", package_name
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))
    log_success("Package update initiated")


def list_erratas(instance_id: str) -> None:
    """List available erratas for an instance."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_info("Listing available erratas...")
    result = run_oci_command([
        "os-management", "managed-instance", "list-available-packages",
        "--managed-instance-id", instance_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for pkg in result["data"]:
            print(f"{pkg['display-name']}\t{pkg['version']}\t{pkg['type']}")


def list_installed_packages(instance_id: str) -> None:
    """List installed packages on an instance."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    log_info("Listing installed packages...")
    result = run_oci_command([
        "os-management", "managed-instance", "list-installed-packages",
        "--managed-instance-id", instance_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for pkg in result["data"]:
            print(f"{pkg['display-name']}\t{pkg['version']}\t{pkg['architecture']}")


def get_work_request(request_id: str) -> None:
    """Get work request status."""
    if not request_id:
        log_error("Work request OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "work-request", "get",
        "--work-request-id", request_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))


def list_work_requests(compartment: Optional[str] = None) -> None:
    """List work requests in compartment."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing work requests...")
    result = run_oci_command([
        "os-management", "work-request", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for request in result["data"]:
            print(f"{request['id']}\t{request['operation-type']}\t{request['status']}\t{request['percent-complete']}%")


def create_scheduled_job(
    compartment: str,
    name: str,
    schedule_type: str,
    operation_type: str,
    instance_id: str
) -> None:
    """Create a scheduled patching job."""
    if not all([compartment, name, schedule_type, operation_type, instance_id]):
        log_error("Usage: create-job <compartment> <name> <schedule_type> <operation_type> <instance_id>")
        sys.exit(1)

    log_info(f"Creating scheduled job: {name}")

    result = run_oci_command([
        "os-management", "scheduled-job", "create",
        "--compartment-id", compartment,
        "--display-name", name,
        "--schedule-type", schedule_type,
        "--operation-type", operation_type,
        "--managed-instance-ids", json.dumps([instance_id])
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))
    log_success(f"Scheduled job created: {name}")


def main():
    """Main entry point."""
    if not check_dependencies(["oci"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI OS Management Patch Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list-instances [compartment]                  List managed instances with update counts
  list-updates <instance_id>                    List available updates
  list-security <instance_id>                   List security updates only
  install-all <instance_id>                     Install all updates
  install-security <instance_id>                Install security updates only
  install-package <instance_id> <package>       Install specific package update
  list-erratas <instance_id>                    List available erratas
  list-packages <instance_id>                   List installed packages
  get-work-request <request_id>                 Get work request status
  list-work-requests [compartment]              List work requests
  create-job <comp> <name> <sched> <op> <inst>  Create scheduled job

Schedule Types: ONETIME, RECURRING
Operation Types: INSTALL_ALL_UPDATES, INSTALL_SECURITY_UPDATES,
                 UPDATE_PACKAGE, REMOVE_PACKAGE

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        "list-instances": lambda a: list_managed_instances(a[0] if a else None),
        "list-updates": lambda a: list_available_updates(a[0]),
        "list-security": lambda a: list_security_updates(a[0]),
        "install-all": lambda a: install_all_updates(a[0]),
        "install-security": lambda a: install_security_updates(a[0]),
        "install-package": lambda a: install_package_update(a[0], a[1]),
        "list-erratas": lambda a: list_erratas(a[0]),
        "list-packages": lambda a: list_installed_packages(a[0]),
        "get-work-request": lambda a: get_work_request(a[0]),
        "list-work-requests": lambda a: list_work_requests(a[0] if a else None),
        "create-job": lambda a: create_scheduled_job(a[0], a[1], a[2], a[3], a[4]),
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
