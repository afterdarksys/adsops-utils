"""Typer sub-app for infractl: remote Docker and k3s management over SSH.

This module is auto-registered by adsops/cli.py via conditional import:
    from adsops.infractl.cli import app as infractl_app

Sub-apps:
    docker  — Docker commands (ls, start, stop, restart, logs, exec)
    k3s     — k3s/kubectl commands (nodes, pods, logs, apply)
"""
import asyncio
import sys
from typing import Annotated, List, Optional

import typer

app = typer.Typer(
    help="Manage remote Docker and k3s infrastructure",
    no_args_is_help=True,
)
docker_app = typer.Typer(help="Docker commands over SSH", no_args_is_help=True)
k3s_app = typer.Typer(help="k3s/kubectl commands over SSH", no_args_is_help=True)

app.add_typer(docker_app, name="docker")
app.add_typer(k3s_app, name="k3s")


# ---------------------------------------------------------------------------
# Docker commands
# ---------------------------------------------------------------------------


@docker_app.command("ls")
def docker_ls_cmd(
    hosts: List[str] = typer.Argument(..., help="Host(s) to query"),
    all_: Annotated[bool, typer.Option("--all", "-a", help="Show all containers (including stopped)")] = False,
) -> None:
    """List Docker containers on remote host(s). Supports multi-host parallel execution (D-07)."""
    from adsops.infractl.ssh import run_parallel_sync

    fmt = r"table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
    flag = "--all " if all_ else ""
    results = run_parallel_sync(hosts, f"docker ps {flag}--format '{fmt}'")
    for item in results:
        if isinstance(item, Exception):
            typer.echo(f"ERROR: {item}", err=True)
        else:
            host, stdout, stderr = item
            if len(hosts) > 1:
                for line in stdout.splitlines():
                    typer.echo(f"[{host}] {line}")
            else:
                typer.echo(stdout, nl=False)
            if stderr:
                typer.echo(stderr, err=True)


@docker_app.command("start")
def docker_start_cmd(
    hosts: List[str] = typer.Argument(..., help="Host(s) followed by container name(s)"),
) -> None:
    """Start one or more containers on remote host(s).

    Usage: adsops infractl docker start <host> <container> [container...]

    For multi-host: pass multiple hosts first, then container names will apply to all.
    Single-host usage: first arg is host, remaining are container names.
    """
    if len(hosts) < 2:
        typer.echo("Usage: docker start <host> <container> [container...]", err=True)
        raise typer.Exit(1)
    host = hosts[0]
    containers = hosts[1:]
    from adsops.infractl.docker import docker_start

    stdout, stderr = docker_start(host, containers)
    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True)


@docker_app.command("stop")
def docker_stop_cmd(
    hosts: List[str] = typer.Argument(..., help="Host followed by container name(s)"),
) -> None:
    """Stop one or more containers on a remote host.

    Usage: adsops infractl docker stop <host> <container> [container...]
    """
    if len(hosts) < 2:
        typer.echo("Usage: docker stop <host> <container> [container...]", err=True)
        raise typer.Exit(1)
    host = hosts[0]
    containers = hosts[1:]
    from adsops.infractl.docker import docker_stop

    stdout, stderr = docker_stop(host, containers)
    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True)


@docker_app.command("restart")
def docker_restart_cmd(
    hosts: List[str] = typer.Argument(..., help="Host followed by container name(s)"),
) -> None:
    """Restart one or more containers on a remote host.

    Usage: adsops infractl docker restart <host> <container> [container...]
    """
    if len(hosts) < 2:
        typer.echo("Usage: docker restart <host> <container> [container...]", err=True)
        raise typer.Exit(1)
    host = hosts[0]
    containers = hosts[1:]
    from adsops.infractl.docker import docker_restart

    stdout, stderr = docker_restart(host, containers)
    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True)


@docker_app.command("logs")
def docker_logs_cmd(
    host: str = typer.Argument(..., help="Remote host"),
    container: str = typer.Argument(..., help="Container name or ID"),
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output")] = False,
    tail: Annotated[str, typer.Option("--tail", help="Number of lines from end")] = "100",
) -> None:
    """Fetch logs from a container on a remote host (streaming)."""
    from adsops.infractl.docker import docker_logs

    docker_logs(host, container, follow=follow, tail=tail)


@docker_app.command("exec")
def docker_exec_cmd(
    host: str = typer.Argument(..., help="Remote host"),
    container: str = typer.Argument(..., help="Container name or ID"),
    cmd: str = typer.Argument("sh", help="Command to execute (default: sh)"),
) -> None:
    """Execute a command in a running container on a remote host (streaming)."""
    from adsops.infractl.docker import docker_exec

    docker_exec(host, container, cmd)


# ---------------------------------------------------------------------------
# k3s commands
# ---------------------------------------------------------------------------


@k3s_app.command("nodes")
def k3s_nodes_cmd(
    hosts: List[str] = typer.Argument(..., help="Host(s) to query"),
    wide: Annotated[bool, typer.Option("--wide", "-w", help="Wide output")] = False,
) -> None:
    """List k3s nodes on remote host(s). Supports multi-host parallel execution (D-07)."""
    from adsops.infractl.ssh import run_parallel_sync

    flags = "get nodes"
    if wide:
        flags += " -o wide"
    results = run_parallel_sync(hosts, f"k3s kubectl {flags}")
    for item in results:
        if isinstance(item, Exception):
            typer.echo(f"ERROR: {item}", err=True)
        else:
            host, stdout, stderr = item
            if len(hosts) > 1:
                for line in stdout.splitlines():
                    typer.echo(f"[{host}] {line}")
            else:
                typer.echo(stdout, nl=False)
            if stderr:
                typer.echo(stderr, err=True)


@k3s_app.command("pods")
def k3s_pods_cmd(
    hosts: List[str] = typer.Argument(..., help="Host(s) to query"),
    namespace: Annotated[str, typer.Option("--namespace", "-n", help="Namespace (default: all)")] = "all",
    wide: Annotated[bool, typer.Option("--wide", "-w", help="Wide output")] = False,
) -> None:
    """List pods on remote k3s cluster(s). Supports multi-host parallel execution (D-07)."""
    from adsops.infractl.ssh import run_parallel_sync

    flags = "get pods"
    if namespace == "all" or namespace == "":
        flags += " -A"
    else:
        flags += f" -n {namespace}"
    if wide:
        flags += " -o wide"
    results = run_parallel_sync(hosts, f"k3s kubectl {flags}")
    for item in results:
        if isinstance(item, Exception):
            typer.echo(f"ERROR: {item}", err=True)
        else:
            host, stdout, stderr = item
            if len(hosts) > 1:
                for line in stdout.splitlines():
                    typer.echo(f"[{host}] {line}")
            else:
                typer.echo(stdout, nl=False)
            if stderr:
                typer.echo(stderr, err=True)


@k3s_app.command("logs")
def k3s_logs_cmd(
    host: str = typer.Argument(..., help="Remote host"),
    pod: str = typer.Argument(..., help="Pod name"),
    namespace: Annotated[str, typer.Option("--namespace", "-n", help="Namespace")] = "",
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output")] = False,
    tail: Annotated[str, typer.Option("--tail", help="Lines from end")] = "100",
) -> None:
    """Fetch logs from a pod on a remote k3s cluster (streaming)."""
    from adsops.infractl.k3s import k3s_logs

    k3s_logs(host, pod, ns=namespace, follow=follow, tail=tail)


@k3s_app.command("apply")
def k3s_apply_cmd(
    host: str = typer.Argument(..., help="Remote host"),
    file: str = typer.Argument(..., help="Path to local YAML manifest file"),
    delete: Annotated[bool, typer.Option("--delete", help="Delete instead of apply")] = False,
) -> None:
    """SCP a manifest to a remote k3s host and apply (or delete) it."""
    from adsops.infractl.k3s import k3s_apply

    k3s_apply(host, file, delete=delete)
