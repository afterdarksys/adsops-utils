#!/usr/bin/env python3
"""
common.py - Shared utilities for OCI operations
After Dark Systems - Ops Utils
"""

import json
import subprocess
import sys
from typing import Any, Optional


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def log_info(message: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def log_success(message: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def log_warn(message: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {message}")


def log_error(message: str) -> None:
    """Print error message in red to stderr."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}", file=sys.stderr)


def run_oci_command(
    args: list[str],
    profile: str = "DEFAULT",
    output_json: bool = True,
    check: bool = True
) -> Optional[dict[str, Any]]:
    """
    Run an OCI CLI command and return parsed JSON output.

    Args:
        args: List of command arguments (without 'oci' prefix)
        profile: OCI CLI profile to use
        output_json: Whether to request JSON output
        check: Whether to raise exception on non-zero exit

    Returns:
        Parsed JSON output if output_json is True, else None
    """
    cmd = ["oci"] + args + ["--profile", profile]
    if output_json:
        cmd.extend(["--output", "json"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        if output_json and result.stdout:
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {' '.join(cmd)}")
        if e.stderr:
            log_error(e.stderr)
        if check:
            raise
        return None
    except json.JSONDecodeError as e:
        log_error(f"Failed to parse JSON output: {e}")
        return None


def check_dependencies(commands: list[str]) -> bool:
    """Check if required commands are available."""
    missing = []
    for cmd in commands:
        try:
            subprocess.run(
                ["which", cmd],
                capture_output=True,
                check=True
            )
        except subprocess.CalledProcessError:
            missing.append(cmd)

    if missing:
        log_error(f"Missing required dependencies: {', '.join(missing)}")
        return False
    return True


def confirm_action(message: str) -> bool:
    """Prompt user for confirmation."""
    response = input(f"{message} (y/N): ")
    return response.lower() in ('y', 'yes')


def format_table(headers: list[str], rows: list[list[str]], separator: str = "\t") -> str:
    """Format data as a simple table."""
    lines = [separator.join(headers)]
    for row in rows:
        lines.append(separator.join(str(cell) for cell in row))
    return "\n".join(lines)
