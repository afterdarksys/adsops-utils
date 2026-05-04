"""k3s/kubectl commands over SSH for infractl.

Provides Python equivalents of the Go infractl k3s subcommands,
executing k3s kubectl commands on remote hosts via asyncssh.

Threat model:
- T-02-06: k3s apply SCP path uses os.path.basename() to prevent path traversal
  in the remote /tmp filename. Local file access is limited to files the user
  already has access to (Typer argument, not shell-expanded).
"""
import asyncio
import os
import sys

import asyncssh

from adsops.infractl.ssh import run_sync, stream_command


def k3s_nodes(host: str, wide: bool = False) -> tuple[str, str]:
    """List k3s nodes on a remote host.

    Args:
        host: Hostname or SSH alias.
        wide: If True, pass -o wide for extended output.

    Returns:
        Tuple of (stdout, stderr) from the remote kubectl get nodes command.
    """
    flags = "get nodes"
    if wide:
        flags += " -o wide"
    return run_sync(host, f"k3s kubectl {flags}")


def k3s_pods(host: str, ns: str = "all", wide: bool = False) -> tuple[str, str]:
    """List pods on a remote k3s cluster.

    Args:
        host: Hostname or SSH alias.
        ns: Namespace. Use "all" for --all-namespaces (-A). Default: "all".
        wide: If True, pass -o wide for extended output.

    Returns:
        Tuple of (stdout, stderr) from the remote kubectl get pods command.
    """
    flags = "get pods"
    if ns == "all" or ns == "":
        flags += " -A"
    else:
        flags += f" -n {ns}"
    if wide:
        flags += " -o wide"
    return run_sync(host, f"k3s kubectl {flags}")


def k3s_logs(
    host: str,
    pod: str,
    ns: str = "",
    follow: bool = False,
    tail: str = "100",
) -> None:
    """Stream logs from a pod on a remote k3s cluster.

    Args:
        host: Hostname or SSH alias.
        pod: Pod name.
        ns: Namespace (optional).
        follow: If True, follow log output (-f flag).
        tail: Number of lines from end (default: 100).
    """
    flags = f"logs {pod}"
    if ns:
        flags += f" -n {ns}"
    if follow:
        flags += " -f"
    if tail:
        flags += f" --tail={tail}"
    asyncio.run(stream_command(host, f"k3s kubectl {flags}"))


def k3s_apply(host: str, local_file: str, delete: bool = False) -> None:
    """SCP a manifest to a remote host and apply or delete it.

    Copies the local file to /tmp/adsops-manifest-{basename} on the remote host
    using os.path.basename() to prevent path traversal (T-02-06), then runs
    k3s kubectl apply|delete -f {remote_path} and cleans up.

    Args:
        host: Hostname or SSH alias.
        local_file: Path to local YAML manifest file.
        delete: If True, use 'delete' instead of 'apply'.
    """
    asyncio.run(_apply(host, local_file, delete))


async def _apply(host: str, local_file: str, delete: bool) -> None:
    """Async implementation of k3s_apply."""
    # Use basename to prevent path traversal in remote /tmp filename (T-02-06)
    remote_tmp = f"/tmp/adsops-manifest-{os.path.basename(local_file)}"
    verb = "delete" if delete else "apply"

    if not os.environ.get("SSH_AUTH_SOCK"):
        raise RuntimeError(
            "No SSH agent found. Run: eval $(ssh-agent) && ssh-add"
        )

    async with asyncssh.connect(host, known_hosts=None) as conn:
        await asyncssh.scp(local_file, (conn, remote_tmp))
        result = await conn.run(
            f"k3s kubectl {verb} -f {remote_tmp} && rm -f {remote_tmp}",
            check=False,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
