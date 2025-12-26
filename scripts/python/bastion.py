#!/usr/bin/env python3
"""
bastion.py - OCI Bastion Service Operations
After Dark Systems - Ops Utils

This module provides functions for managing OCI Bastion sessions
including port forwarding and managed SSH access.
"""

import argparse
import os
import subprocess
import sys
from typing import Optional

from common import (
    check_dependencies, confirm_action, log_error, log_info, log_success,
    log_warn, run_oci_command
)


# Configuration from environment
OCI_PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")
BASTION_OCID = os.environ.get("BASTION_OCID", "")
COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID", "")
DEFAULT_TTL = int(os.environ.get("DEFAULT_TTL", "10800"))  # 3 hours


def list_bastions(compartment: Optional[str] = None) -> None:
    """List bastions in compartment."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing bastions...")
    result = run_oci_command([
        "bastion", "bastion", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for bastion in result["data"]:
            print(f"{bastion['id']}\t{bastion['name']}\t{bastion['bastion-type']}\t{bastion['lifecycle-state']}")


def get_bastion(bastion_id: Optional[str] = None) -> None:
    """Get bastion details."""
    bastion_id = bastion_id or BASTION_OCID
    if not bastion_id:
        log_error("Bastion OCID required.")
        sys.exit(1)

    result = run_oci_command([
        "bastion", "bastion", "get",
        "--bastion-id", bastion_id
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        import json
        print(json.dumps(result["data"], indent=2))


def list_sessions(bastion_id: Optional[str] = None) -> None:
    """List sessions for a bastion."""
    bastion_id = bastion_id or BASTION_OCID
    if not bastion_id:
        log_error("Bastion OCID required.")
        sys.exit(1)

    log_info("Listing sessions...")
    result = run_oci_command([
        "bastion", "session", "list",
        "--bastion-id", bastion_id,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for session in result["data"]:
            print(f"{session['id']}\t{session['display-name']}\t{session['session-type']}\t{session['lifecycle-state']}")


def create_port_forward_session(
    target_host: str,
    target_port: str,
    bastion_id: Optional[str] = None,
    ttl: Optional[int] = None,
    session_name: str = "port-forward-session"
) -> None:
    """Create a port forwarding session."""
    bastion_id = bastion_id or BASTION_OCID
    ttl = ttl or DEFAULT_TTL

    if not bastion_id or not target_host or not target_port:
        log_error("Usage: create-port-forward <target_host> <target_port> [bastion_id] [ttl] [session_name]")
        sys.exit(1)

    log_info(f"Creating port forward session to {target_host}:{target_port}...")

    result = run_oci_command([
        "bastion", "session", "create-port-forwarding",
        "--bastion-id", bastion_id,
        "--target-private-ip", target_host,
        "--target-port", target_port,
        "--session-ttl-in-seconds", str(ttl),
        "--display-name", session_name,
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session_id = result["data"]["id"]
        log_success(f"Session created: {session_id}")
        print(f"\nTo connect, use:")
        print(f"  ssh -N -L <local_port>:{target_host}:{target_port} -p 22 {session_id}@host.bastion.<region>.oci.oraclecloud.com")


def create_managed_ssh_session(
    instance_id: str,
    bastion_id: Optional[str] = None,
    ttl: Optional[int] = None,
    username: str = "opc",
    session_name: str = "managed-ssh-session"
) -> None:
    """Create a managed SSH session to a compute instance."""
    bastion_id = bastion_id or BASTION_OCID
    ttl = ttl or DEFAULT_TTL

    if not bastion_id or not instance_id:
        log_error("Usage: create-managed-ssh <instance_id> [bastion_id] [ttl] [username] [session_name]")
        sys.exit(1)

    log_info(f"Creating managed SSH session to {instance_id}...")

    result = run_oci_command([
        "bastion", "session", "create-managed-ssh",
        "--bastion-id", bastion_id,
        "--target-resource-id", instance_id,
        "--target-os-username", username,
        "--session-ttl-in-seconds", str(ttl),
        "--display-name", session_name,
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session_id = result["data"]["id"]
        ssh_metadata = result["data"].get("ssh-metadata", {})
        log_success(f"Session created: {session_id}")
        if ssh_metadata.get("command"):
            print(f"\nSSH Command:\n  {ssh_metadata['command']}")


def connect_session(session_id: str, local_port: str, ssh_key: str = "~/.ssh/id_rsa") -> None:
    """Connect to an existing session."""
    if not session_id or not local_port:
        log_error("Usage: connect <session_id> <local_port> [ssh_key]")
        sys.exit(1)

    # Get session details
    result = run_oci_command([
        "bastion", "session", "get",
        "--session-id", session_id
    ], profile=OCI_PROFILE)

    if not result or "data" not in result:
        log_error("Failed to get session details")
        sys.exit(1)

    session = result["data"]
    if session["lifecycle-state"] != "ACTIVE":
        log_error(f"Session is not active (state: {session['lifecycle-state']})")
        sys.exit(1)

    ssh_metadata = session.get("ssh-metadata", {})
    command = ssh_metadata.get("command", "")

    if command:
        log_info("Connecting to session...")
        # Replace placeholder with actual values
        command = command.replace("<localPort>", local_port)
        command = command.replace("<privateKey>", os.path.expanduser(ssh_key))
        print(f"Running: {command}")
        os.system(command)
    else:
        log_error("No SSH command available for this session")


def delete_session(session_id: str) -> None:
    """Delete a bastion session."""
    if not session_id:
        log_error("Session OCID required.")
        sys.exit(1)

    log_warn("Deleting session...")
    if not confirm_action("Continue?"):
        log_info("Cancelled.")
        return

    run_oci_command([
        "bastion", "session", "delete",
        "--session-id", session_id,
        "--force"
    ], profile=OCI_PROFILE, output_json=False)

    log_success("Session deleted")


def main():
    """Main entry point."""
    if not check_dependencies(["oci"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI Bastion Service Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list-bastions [compartment]                List bastions
  get-bastion [bastion_id]                   Get bastion details
  list-sessions [bastion_id]                 List sessions
  create-port-forward <host> <port> [...]    Create port forward session
  create-managed-ssh <instance_id> [...]     Create managed SSH session
  connect <session_id> <local_port> [key]    Connect to session
  delete-session <session_id>                Delete session

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  BASTION_OCID      Default bastion OCID
  COMPARTMENT_OCID  Default compartment OCID
  DEFAULT_TTL       Session TTL in seconds (default: 10800)
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        "list-bastions": lambda a: list_bastions(a[0] if a else None),
        "get-bastion": lambda a: get_bastion(a[0] if a else None),
        "list-sessions": lambda a: list_sessions(a[0] if a else None),
        "create-port-forward": lambda a: create_port_forward_session(
            a[0], a[1],
            a[2] if len(a) > 2 else None,
            int(a[3]) if len(a) > 3 else None,
            a[4] if len(a) > 4 else "port-forward-session"
        ),
        "create-managed-ssh": lambda a: create_managed_ssh_session(
            a[0],
            a[1] if len(a) > 1 else None,
            int(a[2]) if len(a) > 2 else None,
            a[3] if len(a) > 3 else "opc",
            a[4] if len(a) > 4 else "managed-ssh-session"
        ),
        "connect": lambda a: connect_session(a[0], a[1], a[2] if len(a) > 2 else "~/.ssh/id_rsa"),
        "delete-session": lambda a: delete_session(a[0]),
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
