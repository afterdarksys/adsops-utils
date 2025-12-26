#!/usr/bin/env python3
"""
osm_session.py - OCI OS Management Session & Agent Operations
After Dark Systems - Ops Utils

This module provides functions for managing OCI OS Management Service
including managed instances, commands, and agents.
"""

import argparse
import json
import os
import sys
from typing import Optional

from common import (
    check_dependencies, log_error, log_info, log_success, run_oci_command
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
            print(f"{instance['id']}\t{instance['display-name']}\t{instance['os-family']}\t{instance['status']}")


def get_managed_instance(instance_id: str) -> None:
    """Get managed instance details."""
    if not instance_id:
        log_error("Managed instance OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "os-management", "managed-instance", "get",
        "--managed-instance-id", instance_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        data = result["data"]
        output = {
            "id": data.get("id"),
            "displayName": data.get("display-name"),
            "osFamily": data.get("os-family"),
            "osVersion": data.get("os-version"),
            "status": data.get("status"),
            "updatesAvailable": data.get("updates-available"),
            "securityUpdatesAvailable": data.get("security-updates-available")
        }
        print(json.dumps(output, indent=2))


def run_command(
    instance_id: str,
    command: str,
    display_name: str = "adhoc-command",
    timeout: int = 3600
) -> None:
    """Run command on instance via Instance Agent."""
    if not instance_id or not command:
        log_error("Usage: run-command <instance_id> <command> [display_name] [timeout]")
        sys.exit(1)

    log_info(f"Running command on instance: {instance_id}")

    result = run_oci_command([
        "compute", "instance-agent", "command", "create",
        "--instance-id", instance_id,
        "--execution-time-out-in-seconds", str(timeout),
        "--display-name", display_name,
        "--content", json.dumps({
            "source": {
                "sourceType": "TEXT",
                "text": command
            },
            "output": {
                "outputType": "TEXT"
            }
        })
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        command_id = result["data"]["id"]
        log_success(f"Command submitted: {command_id}")
        print(f"\nTo check status: python osm_session.py get-command-result {instance_id} {command_id}")


def get_command_result(instance_id: str, command_id: str) -> None:
    """Get command execution result."""
    if not instance_id or not command_id:
        log_error("Usage: get-command-result <instance_id> <command_id>")
        sys.exit(1)

    result = run_oci_command([
        "compute", "instance-agent", "command", "get",
        "--instance-id", instance_id,
        "--command-id", command_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        data = result["data"]
        print(f"Status: {data.get('lifecycle-state')}")

        content = data.get("content", {})
        if content.get("output"):
            output = content["output"]
            if output.get("outputType") == "TEXT":
                print(f"\nOutput:\n{output.get('text', '')}")


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


def list_software_sources(compartment: Optional[str] = None) -> None:
    """List software sources in compartment."""
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


def list_scheduled_jobs(compartment: Optional[str] = None) -> None:
    """List scheduled jobs in compartment."""
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


def get_agent_info(instance_id: str) -> None:
    """Get instance agent information."""
    if not instance_id:
        log_error("Instance OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "compute", "instance", "get",
        "--instance-id", instance_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        data = result["data"]
        agent_config = data.get("agent-config", {})
        print(json.dumps({
            "instanceId": data.get("id"),
            "displayName": data.get("display-name"),
            "agentConfig": {
                "isMonitoringDisabled": agent_config.get("is-monitoring-disabled"),
                "isManagementDisabled": agent_config.get("is-management-disabled"),
                "areAllPluginsDisabled": agent_config.get("are-all-plugins-disabled")
            }
        }, indent=2))


def main():
    """Main entry point."""
    if not check_dependencies(["oci"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI OS Management Session & Agent Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list-instances [compartment]                   List managed instances
  get-instance <instance_id>                     Get instance details
  run-command <instance_id> <command> [name] [timeout]
                                                 Run command on instance
  get-command-result <instance_id> <command_id>  Get command result
  list-work-requests [compartment]               List work requests
  list-sources [compartment]                     List software sources
  list-jobs [compartment]                        List scheduled jobs
  get-agent <instance_id>                        Get agent info

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
        "get-instance": lambda a: get_managed_instance(a[0]),
        "run-command": lambda a: run_command(
            a[0], a[1],
            a[2] if len(a) > 2 else "adhoc-command",
            int(a[3]) if len(a) > 3 else 3600
        ),
        "get-command-result": lambda a: get_command_result(a[0], a[1]),
        "list-work-requests": lambda a: list_work_requests(a[0] if a else None),
        "list-sources": lambda a: list_software_sources(a[0] if a else None),
        "list-jobs": lambda a: list_scheduled_jobs(a[0] if a else None),
        "get-agent": lambda a: get_agent_info(a[0]),
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
