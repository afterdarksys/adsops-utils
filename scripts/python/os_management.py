#!/usr/bin/env python3
"""
os_management.py - OCI OS Management Service Operations
After Dark Systems - Ops Utils

This module provides functions for OCI OS Management Service
including managed instance groups, package management, and compliance.
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


# Managed Instance Group Functions

def list_groups(compartment: Optional[str] = None) -> None:
    """List managed instance groups."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing managed instance groups...")
    result = run_oci_command([
        "os-management", "managed-instance-group", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for group in result["data"]:
            print(f"{group['id']}\t{group['display-name']}\t{group['managed-instance-count']}\t{group['lifecycle-state']}")


def get_group(group_id: str) -> None:
    """Get managed instance group details."""
    if not group_id:
        log_error("Managed instance group OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "managed-instance-group", "get",
        "--managed-instance-group-id", group_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))


def create_group(compartment: str, name: str, description: str = "") -> None:
    """Create managed instance group."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment or not name:
        log_error("Usage: create-group <compartment> <name> [description]")
        sys.exit(1)

    log_info(f"Creating managed instance group: {name}")

    cmd = [
        "os-management", "managed-instance-group", "create",
        "--compartment-id", compartment,
        "--display-name", name
    ]

    if description:
        cmd.extend(["--description", description])

    result = run_oci_command(cmd, profile=OCI_PROFILE)

    if result and "data" in result:
        output = {
            "id": result["data"]["id"],
            "name": result["data"]["display-name"]
        }
        print(json.dumps(output, indent=2))

    log_success(f"Group created: {name}")


def delete_group(group_id: str) -> None:
    """Delete managed instance group."""
    if not group_id:
        log_error("Group OCID required.")
        sys.exit(1)

    log_warn("Deleting managed instance group...")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    run_oci_command([
        "os-management", "managed-instance-group", "delete",
        "--managed-instance-group-id", group_id,
        "--force"
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Group deleted")


def list_group_instances(group_id: str) -> None:
    """List instances in group."""
    if not group_id:
        log_error("Managed instance group OCID required.")
        sys.exit(1)

    log_info("Listing instances in group...")
    result = run_oci_command([
        "os-management", "managed-instance-group", "list-managed-instances",
        "--managed-instance-group-id", group_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for instance in result["data"]:
            print(f"{instance['id']}\t{instance['display-name']}")


def add_to_group(group_id: str, instance_id: str) -> None:
    """Add instance to group."""
    if not group_id or not instance_id:
        log_error("Usage: add-to-group <group_id> <instance_id>")
        sys.exit(1)

    log_info("Adding instance to group...")
    run_oci_command([
        "os-management", "managed-instance-group", "attach-managed-instance",
        "--managed-instance-group-id", group_id,
        "--managed-instance-id", instance_id
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Instance added to group")


def remove_from_group(group_id: str, instance_id: str) -> None:
    """Remove instance from group."""
    if not group_id or not instance_id:
        log_error("Usage: remove-from-group <group_id> <instance_id>")
        sys.exit(1)

    log_info("Removing instance from group...")
    run_oci_command([
        "os-management", "managed-instance-group", "detach-managed-instance",
        "--managed-instance-group-id", group_id,
        "--managed-instance-id", instance_id
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Instance removed from group")


# Package Management Functions

def list_packages(instance_id: str) -> None:
    """List installed packages on instance."""
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


def search_packages(compartment: str, query: str) -> None:
    """Search available packages."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment or not query:
        log_error("Usage: search <compartment> <query>")
        sys.exit(1)

    log_info(f"Searching packages matching: {query}")
    result = run_oci_command([
        "os-management", "software-package", "search",
        "--compartment-id", compartment,
        "--software-package-name", query,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for pkg in result["data"]:
            print(f"{pkg['display-name']}\t{pkg['version']}\t{pkg['type']}")


def install_package(instance_id: str, package_name: str) -> None:
    """Install package on instance."""
    if not instance_id or not package_name:
        log_error("Usage: install <instance_id> <package_name>")
        sys.exit(1)

    log_info(f"Installing package: {package_name}")
    result = run_oci_command([
        "os-management", "managed-instance", "install-package",
        "--managed-instance-id", instance_id,
        "--software-package-name", package_name
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))

    log_success("Package installation initiated")


def remove_package(instance_id: str, package_name: str) -> None:
    """Remove package from instance."""
    if not instance_id or not package_name:
        log_error("Usage: remove <instance_id> <package_name>")
        sys.exit(1)

    log_warn(f"Removing package: {package_name}")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    run_oci_command([
        "os-management", "managed-instance", "remove-package",
        "--managed-instance-id", instance_id,
        "--software-package-name", package_name
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Package removal initiated")


def install_on_group(group_id: str, package_name: str) -> None:
    """Install package on group."""
    if not group_id or not package_name:
        log_error("Usage: install-on-group <group_id> <package_name>")
        sys.exit(1)

    log_info(f"Installing package on group: {package_name}")
    result = run_oci_command([
        "os-management", "managed-instance-group", "install-package",
        "--managed-instance-group-id", group_id,
        "--software-package-name", package_name
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))

    log_success("Group package installation initiated")


# Software Source Functions

def list_sources(compartment: Optional[str] = None) -> None:
    """List software sources."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing software sources...")
    result = run_oci_command([
        "os-management", "software-source", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for source in result["data"]:
            print(f"{source['id']}\t{source['display-name']}\t{source['repo-type']}\t{source['lifecycle-state']}")


def get_source(source_id: str) -> None:
    """Get software source details."""
    if not source_id:
        log_error("Software source OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "software-source", "get",
        "--software-source-id", source_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))


def list_source_packages(source_id: str) -> None:
    """List packages in software source."""
    if not source_id:
        log_error("Software source OCID required.")
        sys.exit(1)

    log_info("Listing packages in software source...")
    result = run_oci_command([
        "os-management", "software-source", "list-packages",
        "--software-source-id", source_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for pkg in result["data"]:
            print(f"{pkg['display-name']}\t{pkg['version']}")


# Scheduled Jobs Functions

def list_jobs(compartment: Optional[str] = None) -> None:
    """List scheduled jobs."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing scheduled jobs...")
    result = run_oci_command([
        "os-management", "scheduled-job", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for job in result["data"]:
            print(f"{job['id']}\t{job['display-name']}\t{job['operation-type']}\t{job['schedule-type']}\t{job['lifecycle-state']}")


def get_job(job_id: str) -> None:
    """Get scheduled job details."""
    if not job_id:
        log_error("Scheduled job OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "scheduled-job", "get",
        "--scheduled-job-id", job_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))


def run_job(job_id: str) -> None:
    """Run scheduled job now."""
    if not job_id:
        log_error("Scheduled job OCID required.")
        sys.exit(1)

    log_info("Running scheduled job now...")
    run_oci_command([
        "os-management", "scheduled-job", "run-now",
        "--scheduled-job-id", job_id
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Scheduled job started")


# Work Request Functions

def list_requests(compartment: Optional[str] = None) -> None:
    """List work requests."""
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


def get_request(request_id: str) -> None:
    """Get work request details."""
    if not request_id:
        log_error("Work request OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "work-request", "get",
        "--work-request-id", request_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))


def main():
    """Main entry point."""
    if not check_dependencies(["oci"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI OS Management Service Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  Managed Instance Groups:
    list-groups [compartment]                  List groups
    get-group <group_id>                       Get group details
    create-group <compartment> <name> [desc]   Create group
    delete-group <group_id>                    Delete group
    group-instances <group_id>                 List instances in group
    add-to-group <group_id> <instance_id>      Add instance to group
    remove-from-group <group_id> <instance_id> Remove instance

  Package Management:
    list-packages <instance_id>                List installed packages
    search <compartment> <query>               Search packages
    install <instance_id> <package>            Install package
    remove <instance_id> <package>             Remove package
    install-on-group <group_id> <package>      Install on group

  Software Sources:
    list-sources [compartment]                 List sources
    get-source <source_id>                     Get source details
    source-packages <source_id>                List packages

  Scheduled Jobs:
    list-jobs [compartment]                    List jobs
    get-job <job_id>                           Get job details
    run-job <job_id>                           Run job now

  Work Requests:
    list-requests [compartment]                List requests
    get-request <request_id>                   Get request details

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        # Groups
        "list-groups": lambda a: list_groups(a[0] if a else None),
        "get-group": lambda a: get_group(a[0]),
        "create-group": lambda a: create_group(a[0], a[1], a[2] if len(a) > 2 else ""),
        "delete-group": lambda a: delete_group(a[0]),
        "group-instances": lambda a: list_group_instances(a[0]),
        "add-to-group": lambda a: add_to_group(a[0], a[1]),
        "remove-from-group": lambda a: remove_from_group(a[0], a[1]),
        # Packages
        "list-packages": lambda a: list_packages(a[0]),
        "search": lambda a: search_packages(a[0], a[1]),
        "install": lambda a: install_package(a[0], a[1]),
        "remove": lambda a: remove_package(a[0], a[1]),
        "install-on-group": lambda a: install_on_group(a[0], a[1]),
        # Sources
        "list-sources": lambda a: list_sources(a[0] if a else None),
        "get-source": lambda a: get_source(a[0]),
        "source-packages": lambda a: list_source_packages(a[0]),
        # Jobs
        "list-jobs": lambda a: list_jobs(a[0] if a else None),
        "get-job": lambda a: get_job(a[0]),
        "run-job": lambda a: run_job(a[0]),
        # Work requests
        "list-requests": lambda a: list_requests(a[0] if a else None),
        "get-request": lambda a: get_request(a[0]),
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
