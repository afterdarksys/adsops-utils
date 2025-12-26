#!/usr/bin/env python3
"""
jump_host.py - OCI Bastion & Jump Host Access
After Dark Systems - Ops Utils

This module provides functions for accessing instances via OCI Bastion
and managing jump host connections.
"""

import argparse
import json
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
SSH_KEY = os.environ.get("SSH_KEY", "~/.ssh/id_rsa")
DEFAULT_USER = os.environ.get("DEFAULT_USER", "opc")
DEFAULT_TTL = int(os.environ.get("DEFAULT_TTL", "10800"))


def list_jump_hosts(compartment: Optional[str] = None, tag_key: str = "role", tag_value: str = "jump-host") -> None:
    """List jump hosts (instances with specific tag)."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info(f"Listing jump hosts (tagged {tag_key}={tag_value})...")
    result = run_oci_command([
        "compute", "instance", "list",
        "--compartment-id", compartment,
        "--lifecycle-state", "RUNNING",
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for instance in result["data"]:
            # Check freeform tags
            freeform_tags = instance.get("freeform-tags", {})
            if freeform_tags.get(tag_key) == tag_value:
                print(f"{instance['id']}\t{instance['display-name']}\t{instance['lifecycle-state']}")


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
            print(f"{bastion['id']}\t{bastion['name']}\t{bastion['lifecycle-state']}")


def connect(
    instance_id: str,
    bastion_id: Optional[str] = None,
    username: str = None,
    ssh_key: str = None
) -> None:
    """Connect to instance via bastion managed SSH session."""
    bastion_id = bastion_id or BASTION_OCID
    username = username or DEFAULT_USER
    ssh_key = ssh_key or SSH_KEY

    if not instance_id or not bastion_id:
        log_error("Usage: connect <instance_id> [bastion_id] [username] [ssh_key]")
        sys.exit(1)

    log_info(f"Creating managed SSH session to {instance_id}...")

    # Create session
    result = run_oci_command([
        "bastion", "session", "create-managed-ssh",
        "--bastion-id", bastion_id,
        "--target-resource-id", instance_id,
        "--target-os-username", username,
        "--session-ttl-in-seconds", str(DEFAULT_TTL),
        "--display-name", "jump-session",
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session = result["data"]
        ssh_metadata = session.get("ssh-metadata", {})
        command = ssh_metadata.get("command", "")

        if command:
            # Replace placeholders
            command = command.replace("<privateKey>", os.path.expanduser(ssh_key))
            log_success(f"Session created: {session['id']}")
            log_info("Connecting...")
            os.system(command)
        else:
            log_warn("No SSH command available. Session ID:")
            print(session["id"])


def port_forward(
    target_host: str,
    target_port: str,
    local_port: str,
    bastion_id: Optional[str] = None,
    ssh_key: str = None
) -> None:
    """Create port forwarding session and connect."""
    bastion_id = bastion_id or BASTION_OCID
    ssh_key = ssh_key or SSH_KEY

    if not target_host or not target_port or not local_port:
        log_error("Usage: port-forward <target_host> <target_port> <local_port> [bastion_id] [ssh_key]")
        sys.exit(1)

    log_info(f"Creating port forward: localhost:{local_port} -> {target_host}:{target_port}")

    # Create session
    result = run_oci_command([
        "bastion", "session", "create-port-forwarding",
        "--bastion-id", bastion_id,
        "--target-private-ip", target_host,
        "--target-port", target_port,
        "--session-ttl-in-seconds", str(DEFAULT_TTL),
        "--display-name", "port-forward-session",
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session = result["data"]
        session_id = session["id"]

        # Get bastion details for endpoint
        bastion_result = run_oci_command([
            "bastion", "bastion", "get",
            "--bastion-id", bastion_id
        ], profile=OCI_PROFILE)

        if bastion_result and "data" in bastion_result:
            bastion_endpoint = bastion_result["data"]["bastion-endpoint"]

            log_success(f"Session created: {session_id}")
            print(f"\nTo connect:")
            print(f"  ssh -N -L {local_port}:{target_host}:{target_port} -p 22 {session_id}@{bastion_endpoint} -i {os.path.expanduser(ssh_key)}")
            print(f"\nOr run:")
            print(f"  python jump_host.py tunnel {session_id} {local_port} {target_host} {target_port}")


def create_session(
    session_type: str,
    target: str,
    port: str = "22",
    bastion_id: Optional[str] = None,
    username: str = None
) -> None:
    """Create bastion session (managed-ssh or port-forwarding)."""
    bastion_id = bastion_id or BASTION_OCID
    username = username or DEFAULT_USER

    if not bastion_id or not target:
        log_error("Usage: create-session <type> <target> [port] [bastion_id] [username]")
        log_error("Types: managed-ssh, port-forward")
        sys.exit(1)

    if session_type == "managed-ssh":
        # target is instance OCID
        result = run_oci_command([
            "bastion", "session", "create-managed-ssh",
            "--bastion-id", bastion_id,
            "--target-resource-id", target,
            "--target-os-username", username,
            "--session-ttl-in-seconds", str(DEFAULT_TTL),
            "--display-name", "managed-ssh-session",
            "--wait-for-state", "ACTIVE"
        ], profile=OCI_PROFILE)
    elif session_type == "port-forward":
        # target is IP address
        result = run_oci_command([
            "bastion", "session", "create-port-forwarding",
            "--bastion-id", bastion_id,
            "--target-private-ip", target,
            "--target-port", port,
            "--session-ttl-in-seconds", str(DEFAULT_TTL),
            "--display-name", "port-forward-session",
            "--wait-for-state", "ACTIVE"
        ], profile=OCI_PROFILE)
    else:
        log_error(f"Unknown session type: {session_type}")
        sys.exit(1)

    if result and "data" in result:
        print(json.dumps(result["data"], indent=2))
        log_success("Session created")


def direct_connect(host: str, username: str = None, ssh_key: str = None, port: str = "22") -> None:
    """Direct SSH connection to jump host."""
    username = username or DEFAULT_USER
    ssh_key = ssh_key or SSH_KEY

    if not host:
        log_error("Usage: direct-connect <host> [username] [ssh_key] [port]")
        sys.exit(1)

    log_info(f"Connecting directly to {username}@{host}:{port}")
    ssh_key = os.path.expanduser(ssh_key)

    os.execvp("ssh", ["ssh", "-i", ssh_key, "-p", port, f"{username}@{host}"])


def tunnel(
    session_id: str,
    local_port: str,
    target_host: str,
    target_port: str,
    ssh_key: str = None
) -> None:
    """Create SSH tunnel using existing session."""
    ssh_key = ssh_key or SSH_KEY

    if not session_id or not local_port or not target_host or not target_port:
        log_error("Usage: tunnel <session_id> <local_port> <target_host> <target_port> [ssh_key]")
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
    bastion_id = session["bastion-id"]

    # Get bastion endpoint
    bastion_result = run_oci_command([
        "bastion", "bastion", "get",
        "--bastion-id", bastion_id
    ], profile=OCI_PROFILE)

    if not bastion_result or "data" not in bastion_result:
        log_error("Failed to get bastion details")
        sys.exit(1)

    bastion_endpoint = bastion_result["data"]["bastion-endpoint"]
    ssh_key = os.path.expanduser(ssh_key)

    log_info(f"Creating tunnel: localhost:{local_port} -> {target_host}:{target_port}")
    log_info("Press Ctrl+C to close tunnel")

    os.execvp("ssh", [
        "ssh", "-N",
        "-L", f"{local_port}:{target_host}:{target_port}",
        "-p", "22",
        f"{session_id}@{bastion_endpoint}",
        "-i", ssh_key
    ])


def proxy(
    instance_id: str,
    bastion_id: Optional[str] = None,
    username: str = None,
    ssh_key: str = None
) -> None:
    """Create dynamic SOCKS proxy through instance."""
    bastion_id = bastion_id or BASTION_OCID
    username = username or DEFAULT_USER
    ssh_key = ssh_key or SSH_KEY

    if not instance_id:
        log_error("Usage: proxy <instance_id> [bastion_id] [username] [ssh_key]")
        sys.exit(1)

    log_info("Creating managed SSH session for SOCKS proxy...")

    # Create session
    result = run_oci_command([
        "bastion", "session", "create-managed-ssh",
        "--bastion-id", bastion_id,
        "--target-resource-id", instance_id,
        "--target-os-username", username,
        "--session-ttl-in-seconds", str(DEFAULT_TTL),
        "--display-name", "socks-proxy-session",
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session = result["data"]
        ssh_metadata = session.get("ssh-metadata", {})
        command = ssh_metadata.get("command", "")

        if command:
            # Modify command to add -D for SOCKS proxy
            command = command.replace("<privateKey>", os.path.expanduser(ssh_key))
            command = command.replace("ssh ", "ssh -D 1080 ")

            log_success(f"Session created: {session['id']}")
            print(f"\nSOCKS proxy command (port 1080):")
            print(f"  {command}")
            print(f"\nOr configure your browser to use SOCKS5 proxy: localhost:1080")


def list_sessions(bastion_id: Optional[str] = None) -> None:
    """List active sessions."""
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


def delete_session(session_id: str) -> None:
    """Delete a session."""
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
    if not check_dependencies(["oci", "ssh"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI Bastion & Jump Host Access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list-jump-hosts [comp] [tag_key] [tag_val]  List tagged jump hosts
  list-bastions [compartment]                  List bastions
  list-sessions [bastion_id]                   List active sessions

  connect <instance_id> [bastion] [user] [key]
                                               Connect via managed SSH
  port-forward <host> <port> <local> [bastion] [key]
                                               Create port forward
  create-session <type> <target> [port] [bastion] [user]
                                               Create session
  direct-connect <host> [user] [key] [port]    Direct SSH connection
  tunnel <session> <local> <host> <port> [key]
                                               Use existing session
  proxy <instance_id> [bastion] [user] [key]   Create SOCKS proxy
  delete-session <session_id>                  Delete session

Session Types: managed-ssh, port-forward

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  BASTION_OCID      Default bastion OCID
  COMPARTMENT_OCID  Default compartment OCID
  SSH_KEY           SSH private key path (default: ~/.ssh/id_rsa)
  DEFAULT_USER      Default SSH username (default: opc)
  DEFAULT_TTL       Session TTL in seconds (default: 10800)
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        "list-jump-hosts": lambda a: list_jump_hosts(
            a[0] if a else None,
            a[1] if len(a) > 1 else "role",
            a[2] if len(a) > 2 else "jump-host"
        ),
        "list-bastions": lambda a: list_bastions(a[0] if a else None),
        "list-sessions": lambda a: list_sessions(a[0] if a else None),
        "connect": lambda a: connect(
            a[0],
            a[1] if len(a) > 1 else None,
            a[2] if len(a) > 2 else None,
            a[3] if len(a) > 3 else None
        ),
        "port-forward": lambda a: port_forward(
            a[0], a[1], a[2],
            a[3] if len(a) > 3 else None,
            a[4] if len(a) > 4 else None
        ),
        "create-session": lambda a: create_session(
            a[0], a[1],
            a[2] if len(a) > 2 else "22",
            a[3] if len(a) > 3 else None,
            a[4] if len(a) > 4 else None
        ),
        "direct-connect": lambda a: direct_connect(
            a[0],
            a[1] if len(a) > 1 else None,
            a[2] if len(a) > 2 else None,
            a[3] if len(a) > 3 else "22"
        ),
        "tunnel": lambda a: tunnel(
            a[0], a[1], a[2], a[3],
            a[4] if len(a) > 4 else None
        ),
        "proxy": lambda a: proxy(
            a[0],
            a[1] if len(a) > 1 else None,
            a[2] if len(a) > 2 else None,
            a[3] if len(a) > 3 else None
        ),
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
