"""Unit tests for the infractl module.

All tests use mocked asyncssh connections so no live SSH hosts are needed.
SSH_AUTH_SOCK is patched via os.environ overrides in fixtures and per-test
decorators to satisfy the SSH agent guard in ssh.py.
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from typer.testing import CliRunner

from adsops.infractl.cli import app


runner = CliRunner()


# ---------------------------------------------------------------------------
# asyncssh mock fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_asyncssh():
    """Patch asyncssh used by adsops.infractl.ssh with a mock connection.

    asyncssh.connect() is used as ``async with asyncssh.connect(...) as conn:``.
    Python evaluates this as: call connect() -> get a context manager, call
    __aenter__ on it.  The connect() call itself is NOT awaited when used with
    ``async with``; the result of connect() must be an async context manager.

    We set connect() to return a MagicMock that supports __aenter__/__aexit__
    as AsyncMocks, with __aenter__ returning the connection mock.

    Yields:
        Tuple of (conn_mock, asyncssh_module_mock)
    """
    with patch("adsops.infractl.ssh.asyncssh") as mock_module:
        conn = AsyncMock()

        result = MagicMock()
        result.stdout = "CONTAINER ID  NAMES  IMAGE  STATUS\nabc123  web  nginx  Up 2h"
        result.stderr = ""
        conn.run = AsyncMock(return_value=result)

        # Build async context manager for the connect() return value
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_module.connect = MagicMock(return_value=cm)

        yield conn, mock_module


# ---------------------------------------------------------------------------
# docker service layer tests
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_docker_ls_returns_output(mock_asyncssh):
    """docker_ls should return stdout from the remote docker ps command."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "CONTAINER ID  NAMES  IMAGE  STATUS\nabc123  web  nginx  Up 2h"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.docker import docker_ls

    stdout, stderr = docker_ls("test-host")
    assert "abc123" in stdout
    assert stderr == ""
    # Verify docker ps command was called
    conn.run.assert_awaited_once()
    cmd_arg = conn.run.call_args[0][0]
    assert "docker ps" in cmd_arg
    assert "--format" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_docker_ls_all_flag(mock_asyncssh):
    """docker_ls with all_containers=True should pass --all to docker ps."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "abc123  web  nginx  Exited (0) 1h"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.docker import docker_ls

    docker_ls("test-host", all_containers=True)
    cmd_arg = conn.run.call_args[0][0]
    assert "--all" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_docker_ls_multi_host(mock_asyncssh):
    """run_parallel_sync should be called with multiple hosts for CLI multi-host ls."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "web  nginx  Up 2h"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.ssh import run_parallel_sync

    results = run_parallel_sync(["host1", "host2"], "docker ps --format 'table'")
    assert len(results) == 2
    # Both hosts should return (host, stdout, stderr) tuples (not exceptions)
    for item in results:
        assert not isinstance(item, Exception)
        host, stdout, stderr = item
        assert host in ("host1", "host2")


# ---------------------------------------------------------------------------
# SSH agent guard tests
# ---------------------------------------------------------------------------


def test_ssh_agent_check_raises_without_sock():
    """run_command should raise RuntimeError when SSH_AUTH_SOCK is not set."""
    import asyncio
    from adsops.infractl.ssh import run_command

    # Ensure SSH_AUTH_SOCK is absent
    env_without_sock = {k: v for k, v in os.environ.items() if k != "SSH_AUTH_SOCK"}
    with patch.dict(os.environ, env_without_sock, clear=True):
        with pytest.raises(RuntimeError, match="No SSH agent found"):
            asyncio.run(run_command("test-host", "echo hi"))


def test_ssh_agent_check_docker_ls():
    """docker_ls should raise RuntimeError when SSH_AUTH_SOCK is not set."""
    from adsops.infractl.docker import docker_ls

    env_without_sock = {k: v for k, v in os.environ.items() if k != "SSH_AUTH_SOCK"}
    with patch.dict(os.environ, env_without_sock, clear=True):
        with pytest.raises(RuntimeError, match="No SSH agent found"):
            docker_ls("test-host")


# ---------------------------------------------------------------------------
# k3s service layer tests
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_nodes_command(mock_asyncssh):
    """k3s_nodes should send 'k3s kubectl get nodes' to the remote host."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "NAME    STATUS  ROLES\nnode1   Ready   master"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_nodes

    stdout, stderr = k3s_nodes("test-host")
    cmd_arg = conn.run.call_args[0][0]
    assert "k3s kubectl" in cmd_arg
    assert "get nodes" in cmd_arg
    assert "node1" in stdout


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_nodes_wide_flag(mock_asyncssh):
    """k3s_nodes with wide=True should add -o wide to the command."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "NAME    STATUS  ROLES"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_nodes

    k3s_nodes("test-host", wide=True)
    cmd_arg = conn.run.call_args[0][0]
    assert "-o wide" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_pods_all_namespaces(mock_asyncssh):
    """k3s_pods with ns='all' should send -A flag."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "NAMESPACE  NAME  READY  STATUS"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_pods

    k3s_pods("test-host", ns="all")
    cmd_arg = conn.run.call_args[0][0]
    assert "-A" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_pods_specific_namespace(mock_asyncssh):
    """k3s_pods with a specific namespace should use -n <ns>."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "NAME  READY"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_pods

    k3s_pods("test-host", ns="kube-system")
    cmd_arg = conn.run.call_args[0][0]
    assert "-n kube-system" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_apply_uses_scp(mock_asyncssh):
    """k3s_apply should call asyncssh.scp with the local file and remote /tmp path."""
    conn, mock_module = mock_asyncssh

    # Mock scp as a coroutine
    mock_module.scp = AsyncMock(return_value=None)

    result_mock = MagicMock()
    result_mock.stdout = "deployment.apps/myapp created"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_apply

    # Also need to patch asyncssh in k3s module
    with patch("adsops.infractl.k3s.asyncssh", mock_module):
        k3s_apply("test-host", "/tmp/mymanifest.yaml", delete=False)

    mock_module.scp.assert_awaited_once()
    scp_args = mock_module.scp.call_args[0]
    # First arg is local file
    assert scp_args[0] == "/tmp/mymanifest.yaml"
    # Second arg is (conn, remote_path) tuple
    assert scp_args[1][1] == "/tmp/adsops-manifest-mymanifest.yaml"

    # kubectl apply command should be called
    conn.run.assert_awaited_once()
    cmd_arg = conn.run.call_args[0][0]
    assert "k3s kubectl apply" in cmd_arg
    assert "mymanifest.yaml" in cmd_arg


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_k3s_apply_delete_verb(mock_asyncssh):
    """k3s_apply with delete=True should use 'delete' instead of 'apply'."""
    conn, mock_module = mock_asyncssh
    mock_module.scp = AsyncMock(return_value=None)

    result_mock = MagicMock()
    result_mock.stdout = "deployment.apps/myapp deleted"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    from adsops.infractl.k3s import k3s_apply

    with patch("adsops.infractl.k3s.asyncssh", mock_module):
        k3s_apply("test-host", "/tmp/mymanifest.yaml", delete=True)

    cmd_arg = conn.run.call_args[0][0]
    assert "k3s kubectl delete" in cmd_arg


# ---------------------------------------------------------------------------
# CLI routing tests
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_cli_docker_ls_routing(mock_asyncssh):
    """CliRunner: 'infractl docker ls test-host' should output docker ps results."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "abc123  web  nginx  Up 2h\n"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    result = runner.invoke(app, ["docker", "ls", "test-host"])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "abc123" in result.output or result.output.strip() != ""


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_cli_k3s_nodes_routing(mock_asyncssh):
    """CliRunner: 'infractl k3s nodes test-host' should execute kubectl get nodes."""
    conn, mock_module = mock_asyncssh
    result_mock = MagicMock()
    result_mock.stdout = "NAME  STATUS  ROLES\nnode1  Ready  master\n"
    result_mock.stderr = ""
    conn.run = AsyncMock(return_value=result_mock)

    result = runner.invoke(app, ["k3s", "nodes", "test-host"])
    assert result.exit_code == 0, f"CLI failed: {result.output}"


def test_cli_docker_help():
    """'infractl docker --help' should show docker subcommands."""
    result = runner.invoke(app, ["docker", "--help"])
    assert result.exit_code == 0
    assert "ls" in result.output
    assert "logs" in result.output
    assert "exec" in result.output


def test_cli_k3s_help():
    """'infractl k3s --help' should show k3s subcommands."""
    result = runner.invoke(app, ["k3s", "--help"])
    assert result.exit_code == 0
    assert "nodes" in result.output
    assert "pods" in result.output
    assert "apply" in result.output


# ---------------------------------------------------------------------------
# Input validation tests (T-02-05)
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_docker_invalid_container_name_rejected():
    """Container names with shell metacharacters should raise ValueError."""
    from adsops.infractl.docker import docker_start

    with pytest.raises(ValueError, match="Invalid container name"):
        docker_start("test-host", ["web; rm -rf /"])


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"})
def test_docker_invalid_host_rejected():
    """Hostnames with shell metacharacters should raise ValueError."""
    from adsops.infractl.docker import docker_ls

    with pytest.raises(ValueError, match="Invalid hostname"):
        docker_ls("host; rm -rf /")
