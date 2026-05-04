"""asyncssh connection layer for infractl remote command execution.

Design decisions (per threat model):
- T-02-07: known_hosts=None — acceptable for internal tooling where hosts are
  in ~/.ssh/config; SSH agent auth ensures only trusted identities are used.
- T-02-08: asyncio.gather with return_exceptions=True prevents one failed host
  from blocking parallel multi-host execution.
- SSH_AUTH_SOCK guard: fail fast with clear message when SSH agent is unavailable.
"""
import asyncio
import os
import sys

import asyncssh


async def run_command(host: str, command: str) -> tuple[str, str]:
    """Run a command on a remote host via SSH agent auth (D-05).

    Args:
        host: Hostname or SSH alias from ~/.ssh/config.
        command: Shell command string to execute on the remote host.

    Returns:
        Tuple of (stdout, stderr) strings.

    Raises:
        RuntimeError: If SSH_AUTH_SOCK is not set (no SSH agent running).
    """
    if not os.environ.get("SSH_AUTH_SOCK"):
        raise RuntimeError(
            "No SSH agent found. Run: eval $(ssh-agent) && ssh-add"
        )
    async with asyncssh.connect(host, known_hosts=None) as conn:
        result = await conn.run(command, check=False)
        return result.stdout or "", result.stderr or ""


async def stream_command(host: str, command: str) -> None:
    """Stream command output line-by-line to stdout/stderr (for logs -f, exec).

    Args:
        host: Hostname or SSH alias.
        command: Shell command string to execute and stream output from.

    Raises:
        RuntimeError: If SSH_AUTH_SOCK is not set (no SSH agent running).
    """
    if not os.environ.get("SSH_AUTH_SOCK"):
        raise RuntimeError(
            "No SSH agent found. Run: eval $(ssh-agent) && ssh-add"
        )
    async with asyncssh.connect(host, known_hosts=None) as conn:
        async with conn.create_process(command) as proc:
            async for line in proc.stdout:
                print(f"[{host}] {line}", end="")
            async for line in proc.stderr:
                print(f"[{host}] ERR: {line}", end="", file=sys.stderr)


async def run_parallel(
    hosts: list[str], command: str
) -> list[tuple[str, str, str] | Exception]:
    """Run the same command on multiple hosts in parallel (D-07).

    Uses asyncio.gather with return_exceptions=True so one failed host does not
    block the others (T-02-08 mitigation).

    Args:
        hosts: List of hostnames or SSH aliases.
        command: Shell command to execute on each host.

    Returns:
        List of (host, stdout, stderr) tuples or Exception objects for failures.
    """

    async def _run(h: str) -> tuple[str, str, str]:
        stdout, stderr = await run_command(h, command)
        return h, stdout, stderr

    return await asyncio.gather(*[_run(h) for h in hosts], return_exceptions=True)


def run_sync(host: str, command: str) -> tuple[str, str]:
    """Synchronous wrapper for Typer commands (D-06).

    Args:
        host: Hostname or SSH alias.
        command: Shell command to execute.

    Returns:
        Tuple of (stdout, stderr) strings.
    """
    return asyncio.run(run_command(host, command))


def run_parallel_sync(
    hosts: list[str], command: str
) -> list[tuple[str, str, str] | Exception]:
    """Synchronous multi-host wrapper (D-06 + D-07).

    Args:
        hosts: List of hostnames or SSH aliases.
        command: Shell command to execute on each host.

    Returns:
        List of (host, stdout, stderr) tuples or Exception objects for failures.
    """
    return asyncio.run(run_parallel(hosts, command))
