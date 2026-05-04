"""Lightweight SSH config file parser.

Parses ~/.ssh/config for Host, HostName, User, Port directives.
Handles Include directives by expanding paths. Skips wildcard hosts (Host *).
"""
import glob
import os
from typing import Optional


def _parse_file(path: str, visited: Optional[set] = None) -> list[dict]:
    """Parse a single SSH config file, returning list of host entry dicts."""
    if visited is None:
        visited = set()

    # Avoid infinite include loops
    real_path = os.path.realpath(path)
    if real_path in visited:
        return []
    visited.add(real_path)

    if not os.path.isfile(path):
        return []

    hosts = []
    current: Optional[dict] = None

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Split keyword from value (case-insensitive keyword)
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        keyword, value = parts[0].lower(), parts[1].strip()

        if keyword == "include":
            # Expand glob patterns relative to ~/.ssh/
            expanded = os.path.expanduser(value)
            if not os.path.isabs(expanded):
                expanded = os.path.join(os.path.expanduser("~/.ssh"), expanded)
            for inc_path in sorted(glob.glob(expanded)):
                hosts.extend(_parse_file(inc_path, visited))

        elif keyword == "host":
            # Save previous host block
            if current is not None:
                hosts.append(current)
            # Skip wildcard blocks
            if value == "*" or "*" in value.split():
                current = None
            else:
                current = {"host": value}

        elif current is not None:
            if keyword == "hostname":
                current["hostname"] = value
            elif keyword == "user":
                current["user"] = value
            elif keyword == "port":
                current["port"] = value

    # Save last host block
    if current is not None:
        hosts.append(current)

    return hosts


def parse_ssh_config(path: str = "~/.ssh/config") -> list[dict]:
    """Parse SSH config file and return list of host entry dicts.

    Each dict has: host (alias), hostname (optional), user (optional), port (optional).
    Wildcard hosts (Host *) are skipped. Include directives are expanded.
    """
    expanded = os.path.expanduser(path)
    return _parse_file(expanded)
