#!/usr/bin/env python3
"""
backend_sessions.py - OCI Backend Service Session Management
After Dark Systems - Ops Utils

This module provides functions for managing connections to backend services
via OCI Bastion, including databases and other services.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
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
DEFAULT_TTL = int(os.environ.get("DEFAULT_TTL", "10800"))

# Tunnel tracking directory
TUNNEL_DIR = Path(os.environ.get("TUNNEL_DIR", "/tmp/oci-tunnels"))


def ensure_tunnel_dir() -> None:
    """Ensure tunnel tracking directory exists."""
    TUNNEL_DIR.mkdir(parents=True, exist_ok=True)


# Database Discovery Functions

def list_autonomous_dbs(compartment: Optional[str] = None) -> None:
    """List Autonomous Databases."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing Autonomous Databases...")
    result = run_oci_command([
        "db", "autonomous-database", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for db in result["data"]:
            print(f"{db['id']}\t{db['display-name']}\t{db['db-workload']}\t{db['lifecycle-state']}")


def list_mysql_dbs(compartment: Optional[str] = None) -> None:
    """List MySQL Database Systems."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing MySQL Database Systems...")
    result = run_oci_command([
        "mysql", "db-system", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for db in result["data"]:
            print(f"{db['id']}\t{db['display-name']}\t{db['lifecycle-state']}")


def list_postgres_dbs(compartment: Optional[str] = None) -> None:
    """List PostgreSQL Database Systems."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing PostgreSQL Database Systems...")
    result = run_oci_command([
        "psql", "db-system", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for db in result["data"]:
            print(f"{db['id']}\t{db['display-name']}\t{db['lifecycle-state']}")


def list_nosql_tables(compartment: Optional[str] = None) -> None:
    """List NoSQL Tables."""
    compartment = compartment or COMPARTMENT_OCID
    if not compartment:
        log_error("Compartment OCID required.")
        sys.exit(1)

    log_info("Listing NoSQL Tables...")
    result = run_oci_command([
        "nosql", "table", "list",
        "--compartment-id", compartment,
        "--all"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        for table in result["data"]:
            print(f"{table['id']}\t{table['name']}\t{table['lifecycle-state']}")


# Bastion Session Functions

def create_port_forward_session(
    target_host: str,
    target_port: str,
    session_name: str = "backend-session",
    bastion_id: Optional[str] = None
) -> Optional[str]:
    """Create bastion port forwarding session."""
    bastion_id = bastion_id or BASTION_OCID
    if not bastion_id or not target_host or not target_port:
        log_error("Bastion ID, target host, and target port required")
        return None

    log_info(f"Creating port forward session to {target_host}:{target_port}...")

    result = run_oci_command([
        "bastion", "session", "create-port-forwarding",
        "--bastion-id", bastion_id,
        "--target-private-ip", target_host,
        "--target-port", target_port,
        "--session-ttl-in-seconds", str(DEFAULT_TTL),
        "--display-name", session_name,
        "--wait-for-state", "ACTIVE"
    ], profile=OCI_PROFILE)

    if result and "data" in result:
        session_id = result["data"]["id"]
        log_success(f"Session created: {session_id}")
        return session_id

    return None


def start_tunnel(
    session_id: str,
    local_port: str,
    target_host: str,
    target_port: str,
    ssh_key: str = None,
    background: bool = True
) -> Optional[int]:
    """Start SSH tunnel using bastion session."""
    ssh_key = ssh_key or SSH_KEY

    # Get session details
    result = run_oci_command([
        "bastion", "session", "get",
        "--session-id", session_id
    ], profile=OCI_PROFILE)

    if not result or "data" not in result:
        log_error("Failed to get session details")
        return None

    session = result["data"]
    bastion_id = session["bastion-id"]

    # Get bastion endpoint
    bastion_result = run_oci_command([
        "bastion", "bastion", "get",
        "--bastion-id", bastion_id
    ], profile=OCI_PROFILE)

    if not bastion_result or "data" not in bastion_result:
        log_error("Failed to get bastion details")
        return None

    bastion_endpoint = bastion_result["data"]["bastion-endpoint"]
    ssh_key = os.path.expanduser(ssh_key)

    ssh_cmd = [
        "ssh", "-N",
        "-L", f"{local_port}:{target_host}:{target_port}",
        "-p", "22",
        f"{session_id}@{bastion_endpoint}",
        "-i", ssh_key,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null"
    ]

    if background:
        ensure_tunnel_dir()
        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Save tunnel info
        tunnel_file = TUNNEL_DIR / f"tunnel-{local_port}.json"
        with open(tunnel_file, 'w') as f:
            json.dump({
                "pid": process.pid,
                "session_id": session_id,
                "local_port": local_port,
                "target_host": target_host,
                "target_port": target_port,
                "bastion_endpoint": bastion_endpoint
            }, f)

        log_success(f"Tunnel started (PID: {process.pid})")
        log_info(f"Connect to: localhost:{local_port}")
        return process.pid
    else:
        log_info(f"Starting tunnel: localhost:{local_port} -> {target_host}:{target_port}")
        log_info("Press Ctrl+C to close")
        os.execvp("ssh", ssh_cmd)


def list_tunnels() -> None:
    """List active tunnels."""
    ensure_tunnel_dir()

    tunnels = list(TUNNEL_DIR.glob("tunnel-*.json"))
    if not tunnels:
        log_info("No active tunnels")
        return

    log_info("Active tunnels:")
    for tunnel_file in tunnels:
        with open(tunnel_file) as f:
            data = json.load(f)

        # Check if process is still running
        pid = data["pid"]
        try:
            os.kill(pid, 0)
            status = "RUNNING"
        except OSError:
            status = "DEAD"
            tunnel_file.unlink()  # Clean up dead tunnel file

        if status == "RUNNING":
            print(f"{pid}\tlocalhost:{data['local_port']}\t->\t{data['target_host']}:{data['target_port']}\t{status}")


def close_tunnel(local_port: str) -> None:
    """Close tunnel by local port."""
    ensure_tunnel_dir()

    tunnel_file = TUNNEL_DIR / f"tunnel-{local_port}.json"
    if not tunnel_file.exists():
        log_error(f"No tunnel found on port {local_port}")
        return

    with open(tunnel_file) as f:
        data = json.load(f)

    pid = data["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
        log_success(f"Tunnel closed (PID: {pid})")
    except OSError as e:
        log_warn(f"Process may already be dead: {e}")

    tunnel_file.unlink()


def close_all_tunnels() -> None:
    """Close all tunnels."""
    ensure_tunnel_dir()

    tunnels = list(TUNNEL_DIR.glob("tunnel-*.json"))
    if not tunnels:
        log_info("No tunnels to close")
        return

    for tunnel_file in tunnels:
        with open(tunnel_file) as f:
            data = json.load(f)

        try:
            os.kill(data["pid"], signal.SIGTERM)
            log_success(f"Closed tunnel on port {data['local_port']}")
        except OSError:
            pass

        tunnel_file.unlink()


# Database Connection Helpers

def connect_postgres(
    host: str,
    port: str,
    database: str,
    username: str,
    local_port: str = None,
    bastion_id: Optional[str] = None
) -> None:
    """Connect to PostgreSQL via bastion tunnel."""
    if not all([host, port, database, username]):
        log_error("Usage: connect-postgres <host> <port> <database> <username> [local_port] [bastion_id]")
        sys.exit(1)

    local_port = local_port or port

    # Create session and tunnel
    session_id = create_port_forward_session(host, port, "postgres-session", bastion_id)
    if not session_id:
        sys.exit(1)

    pid = start_tunnel(session_id, local_port, host, port, background=True)
    if not pid:
        sys.exit(1)

    # Wait for tunnel to establish
    time.sleep(2)

    log_info(f"Connecting to PostgreSQL...")
    os.system(f"psql -h localhost -p {local_port} -U {username} -d {database}")


def connect_mysql(
    host: str,
    port: str,
    database: str,
    username: str,
    local_port: str = None,
    bastion_id: Optional[str] = None
) -> None:
    """Connect to MySQL via bastion tunnel."""
    if not all([host, port, database, username]):
        log_error("Usage: connect-mysql <host> <port> <database> <username> [local_port] [bastion_id]")
        sys.exit(1)

    local_port = local_port or port

    # Create session and tunnel
    session_id = create_port_forward_session(host, port, "mysql-session", bastion_id)
    if not session_id:
        sys.exit(1)

    pid = start_tunnel(session_id, local_port, host, port, background=True)
    if not pid:
        sys.exit(1)

    # Wait for tunnel to establish
    time.sleep(2)

    log_info(f"Connecting to MySQL...")
    os.system(f"mysql -h 127.0.0.1 -P {local_port} -u {username} -p {database}")


def connect_redis(
    host: str,
    port: str = "6379",
    local_port: str = None,
    bastion_id: Optional[str] = None
) -> None:
    """Connect to Redis via bastion tunnel."""
    if not host:
        log_error("Usage: connect-redis <host> [port] [local_port] [bastion_id]")
        sys.exit(1)

    local_port = local_port or port

    # Create session and tunnel
    session_id = create_port_forward_session(host, port, "redis-session", bastion_id)
    if not session_id:
        sys.exit(1)

    pid = start_tunnel(session_id, local_port, host, port, background=True)
    if not pid:
        sys.exit(1)

    # Wait for tunnel to establish
    time.sleep(2)

    log_info(f"Connecting to Redis...")
    os.system(f"redis-cli -h 127.0.0.1 -p {local_port}")


def connect_mongodb(
    host: str,
    port: str = "27017",
    database: str = "admin",
    local_port: str = None,
    bastion_id: Optional[str] = None
) -> None:
    """Connect to MongoDB via bastion tunnel."""
    if not host:
        log_error("Usage: connect-mongodb <host> [port] [database] [local_port] [bastion_id]")
        sys.exit(1)

    local_port = local_port or port

    # Create session and tunnel
    session_id = create_port_forward_session(host, port, "mongodb-session", bastion_id)
    if not session_id:
        sys.exit(1)

    pid = start_tunnel(session_id, local_port, host, port, background=True)
    if not pid:
        sys.exit(1)

    # Wait for tunnel to establish
    time.sleep(2)

    log_info(f"Connecting to MongoDB...")
    os.system(f"mongosh mongodb://127.0.0.1:{local_port}/{database}")


def quick_tunnel(
    target_host: str,
    target_port: str,
    local_port: str = None,
    bastion_id: Optional[str] = None
) -> None:
    """Quick tunnel setup (create session + start tunnel)."""
    if not target_host or not target_port:
        log_error("Usage: quick-tunnel <target_host> <target_port> [local_port] [bastion_id]")
        sys.exit(1)

    local_port = local_port or target_port

    session_id = create_port_forward_session(target_host, target_port, "quick-tunnel", bastion_id)
    if not session_id:
        sys.exit(1)

    start_tunnel(session_id, local_port, target_host, target_port, background=True)


def main():
    """Main entry point."""
    if not check_dependencies(["oci", "ssh"]):
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="OCI Backend Service Session Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  Database Discovery:
    list-autonomous [compartment]              List Autonomous DBs
    list-mysql [compartment]                   List MySQL DBs
    list-postgres [compartment]                List PostgreSQL DBs
    list-nosql [compartment]                   List NoSQL tables

  Tunnel Management:
    quick-tunnel <host> <port> [local] [bastion]
                                               Quick tunnel setup
    list-tunnels                               List active tunnels
    close-tunnel <local_port>                  Close tunnel
    close-all                                  Close all tunnels

  Database Connections:
    connect-postgres <host> <port> <db> <user> [local] [bastion]
    connect-mysql <host> <port> <db> <user> [local] [bastion]
    connect-redis <host> [port] [local] [bastion]
    connect-mongodb <host> [port] [db] [local] [bastion]

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  BASTION_OCID      Default bastion OCID
  COMPARTMENT_OCID  Default compartment OCID
  SSH_KEY           SSH private key (default: ~/.ssh/id_rsa)
  DEFAULT_TTL       Session TTL in seconds (default: 10800)
  TUNNEL_DIR        Tunnel tracking directory (default: /tmp/oci-tunnels)
"""
    )
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    commands = {
        # Discovery
        "list-autonomous": lambda a: list_autonomous_dbs(a[0] if a else None),
        "list-mysql": lambda a: list_mysql_dbs(a[0] if a else None),
        "list-postgres": lambda a: list_postgres_dbs(a[0] if a else None),
        "list-nosql": lambda a: list_nosql_tables(a[0] if a else None),
        # Tunnels
        "quick-tunnel": lambda a: quick_tunnel(
            a[0], a[1],
            a[2] if len(a) > 2 else None,
            a[3] if len(a) > 3 else None
        ),
        "list-tunnels": lambda a: list_tunnels(),
        "close-tunnel": lambda a: close_tunnel(a[0]),
        "close-all": lambda a: close_all_tunnels(),
        # Connections
        "connect-postgres": lambda a: connect_postgres(
            a[0], a[1], a[2], a[3],
            a[4] if len(a) > 4 else None,
            a[5] if len(a) > 5 else None
        ),
        "connect-mysql": lambda a: connect_mysql(
            a[0], a[1], a[2], a[3],
            a[4] if len(a) > 4 else None,
            a[5] if len(a) > 5 else None
        ),
        "connect-redis": lambda a: connect_redis(
            a[0],
            a[1] if len(a) > 1 else "6379",
            a[2] if len(a) > 2 else None,
            a[3] if len(a) > 3 else None
        ),
        "connect-mongodb": lambda a: connect_mongodb(
            a[0],
            a[1] if len(a) > 1 else "27017",
            a[2] if len(a) > 2 else "admin",
            a[3] if len(a) > 3 else None,
            a[4] if len(a) > 4 else None
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
