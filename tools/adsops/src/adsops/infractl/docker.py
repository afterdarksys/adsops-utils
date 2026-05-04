"""Docker commands over SSH for infractl.

Provides Python equivalents of the Go infractl docker subcommands,
executing docker CLI commands on remote hosts via asyncssh.

Threat model:
- T-02-05: Container names are passed as separate arguments; validate names
  contain only [a-zA-Z0-9_.-] to prevent shell injection when composing
  command strings. Hosts are validated to contain no shell metacharacters.
"""
import asyncio
import re
import sys

from adsops.infractl.ssh import run_sync, stream_command

# Safe hostname pattern: alphanumeric, dots, hyphens, underscores (no shell metacharacters)
_SAFE_HOST_RE = re.compile(r"^[a-zA-Z0-9._\-]+$")
# Safe container/image name pattern (Docker naming rules + subset of image tag chars)
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-/:@]+$")


def _validate_host(host: str) -> None:
    """Raise ValueError if host contains shell metacharacters (T-02-05)."""
    if not _SAFE_HOST_RE.match(host):
        raise ValueError(
            f"Invalid hostname {host!r}: must match [a-zA-Z0-9._-]"
        )


def _validate_name(name: str, label: str = "name") -> None:
    """Raise ValueError if a container/image name contains shell metacharacters."""
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {label} {name!r}: must match [a-zA-Z0-9_.\\-/:@]"
        )


_DOCKER_PS_FORMAT = (
    r"table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
)


def docker_ls(host: str, all_containers: bool = False) -> tuple[str, str]:
    """List Docker containers on a remote host.

    Args:
        host: Hostname or SSH alias.
        all_containers: If True, pass --all flag to show stopped containers.

    Returns:
        Tuple of (stdout, stderr) from the remote docker ps command.
    """
    _validate_host(host)
    flag = "--all " if all_containers else ""
    cmd = f"docker ps {flag}--format '{_DOCKER_PS_FORMAT}'"
    return run_sync(host, cmd)


def docker_start(host: str, containers: list[str]) -> tuple[str, str]:
    """Start one or more containers on a remote host.

    Args:
        host: Hostname or SSH alias.
        containers: List of container names to start.

    Returns:
        Tuple of (stdout, stderr) from the remote docker start command.
    """
    _validate_host(host)
    for c in containers:
        _validate_name(c, "container name")
    names = " ".join(containers)
    return run_sync(host, f"docker start {names}")


def docker_stop(host: str, containers: list[str]) -> tuple[str, str]:
    """Stop one or more containers on a remote host.

    Args:
        host: Hostname or SSH alias.
        containers: List of container names to stop.

    Returns:
        Tuple of (stdout, stderr) from the remote docker stop command.
    """
    _validate_host(host)
    for c in containers:
        _validate_name(c, "container name")
    names = " ".join(containers)
    return run_sync(host, f"docker stop {names}")


def docker_restart(host: str, containers: list[str]) -> tuple[str, str]:
    """Restart one or more containers on a remote host.

    Args:
        host: Hostname or SSH alias.
        containers: List of container names to restart.

    Returns:
        Tuple of (stdout, stderr) from the remote docker restart command.
    """
    _validate_host(host)
    for c in containers:
        _validate_name(c, "container name")
    names = " ".join(containers)
    return run_sync(host, f"docker restart {names}")


def docker_logs(
    host: str,
    container: str,
    follow: bool = False,
    tail: str = "100",
) -> None:
    """Stream logs from a container on a remote host.

    Args:
        host: Hostname or SSH alias.
        container: Container name or ID.
        follow: If True, follow log output (-f flag).
        tail: Number of lines from end to show (default: 100).
    """
    _validate_host(host)
    _validate_name(container, "container name")
    flags = ""
    if follow:
        flags += " -f"
    if tail:
        flags += f" --tail {tail}"
    cmd = f"docker logs{flags} {container}"
    asyncio.run(stream_command(host, cmd))


def docker_exec(host: str, container: str, cmd: str = "sh") -> None:
    """Execute a command in a running container on a remote host.

    Args:
        host: Hostname or SSH alias.
        container: Container name or ID.
        cmd: Command to run inside the container (default: sh).
    """
    _validate_host(host)
    _validate_name(container, "container name")
    asyncio.run(stream_command(host, f"docker exec {container} {cmd}"))
