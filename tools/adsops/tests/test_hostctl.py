"""Unit tests for hostctl module — all DB interaction is mocked."""
import datetime
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from adsops.v1 import host_pb2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resource(**kwargs) -> MagicMock:
    """Construct a mock Resource ORM object with sensible defaults.

    Uses MagicMock rather than instantiating the actual SQLAlchemy ORM class
    without a session — avoids InstrumentedAttribute initialization errors.
    """
    defaults = dict(
        id=1,
        resource_name="test-host",
        hostname="test-host.example.com",
        type="server",
        provider="onprem",
        region=None,
        status="active",
        environment="production",
        owners=["alice"],
        mail_groups=["ops@example.com"],
        metadata_={"key": "value"},
        average_daily_cost=None,
        average_monthly_cost=None,
        external_id=None,
        external_url=None,
        created_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2026, 1, 2, 0, 0, 0),
    )
    defaults.update(kwargs)
    # Use plain MagicMock (no spec) — avoids SQLAlchemy ORM instrumentation
    # issues that occur when creating Resource.__new__ without a session.
    r = MagicMock()
    for k, v in defaults.items():
        setattr(r, k, v)
    return r


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------


def test_list_resources_empty(mock_db_session):
    """Empty DB returns empty list."""
    mock_db_session.scalars.return_value.all.return_value = []

    from adsops.hostctl.service import list_resources

    result = list_resources()
    assert result == []


def test_list_resources_with_filter(mock_db_session):
    """list_resources with filter returns proto records."""
    r = _make_resource(hostname="web1.example.com", status="active")
    mock_db_session.scalars.return_value.all.return_value = [r]

    from adsops.hostctl.service import list_resources

    result = list_resources(status="active")
    assert len(result) == 1
    assert result[0].hostname == "web1.example.com"
    assert result[0].status == "active"


def test_list_resources_proto_conversion(mock_db_session):
    """_to_proto maps owners, mail_groups, and metadata correctly."""
    r = _make_resource(
        owners=["alice", "bob"],
        mail_groups=["ops@example.com"],
        metadata_={"tier": "prod"},
    )
    mock_db_session.scalars.return_value.all.return_value = [r]

    from adsops.hostctl.service import list_resources

    result = list_resources()
    assert len(result) == 1
    rec = result[0]
    assert list(rec.owners) == ["alice", "bob"]
    assert list(rec.mail_groups) == ["ops@example.com"]
    # metadata maps through ParseDict into proto Struct
    assert rec.metadata["tier"] == "prod"


def test_add_resource_validation(mock_db_session):
    """add_resource raises ValueError on invalid type."""
    from adsops.hostctl.service import add_resource

    with pytest.raises(ValueError, match="invalid type"):
        add_resource(
            hostname="bad.example.com",
            type_="mainframe",  # not in VALID_TYPES
            provider="onprem",
            environment="production",
        )


def test_add_resource_invalid_provider(mock_db_session):
    """add_resource raises ValueError on invalid provider."""
    from adsops.hostctl.service import add_resource

    with pytest.raises(ValueError, match="invalid provider"):
        add_resource(
            hostname="host.example.com",
            type_="server",
            provider="aws",  # not in VALID_PROVIDERS
            environment="production",
        )


def test_add_resource_invalid_environment(mock_db_session):
    """add_resource raises ValueError on invalid environment."""
    from adsops.hostctl.service import add_resource

    with pytest.raises(ValueError, match="invalid environment"):
        add_resource(
            hostname="host.example.com",
            type_="server",
            provider="onprem",
            environment="local",  # not in VALID_ENVIRONMENTS
        )


# ---------------------------------------------------------------------------
# SSH config parsing tests
# ---------------------------------------------------------------------------


def test_ssh_config_parse():
    """parse_ssh_config extracts Host/HostName/User/Port from temp file."""
    config_content = """\
Host myserver
    HostName 192.168.1.100
    User deploy
    Port 2222

Host wildcard-skip
    HostName 10.0.0.1
    User root

Host *
    ServerAliveInterval 60
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
        f.write(config_content)
        tmp_path = f.name

    try:
        from adsops.hostctl.ssh_config import parse_ssh_config

        hosts = parse_ssh_config(tmp_path)
        assert len(hosts) == 2
        assert hosts[0]["host"] == "myserver"
        assert hosts[0]["hostname"] == "192.168.1.100"
        assert hosts[0]["user"] == "deploy"
        assert hosts[0]["port"] == "2222"
        assert hosts[1]["host"] == "wildcard-skip"
    finally:
        os.unlink(tmp_path)


def test_ssh_config_skips_wildcard():
    """parse_ssh_config does not include Host * blocks."""
    config_content = """\
Host *
    ServerAliveInterval 60
    ConnectTimeout 10
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
        f.write(config_content)
        tmp_path = f.name

    try:
        from adsops.hostctl.ssh_config import parse_ssh_config

        hosts = parse_ssh_config(tmp_path)
        assert hosts == []
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Probe tests
# ---------------------------------------------------------------------------


def test_probe_host_reachable():
    """probe_host returns reachable=True when SSH connection succeeds."""
    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=MagicMock())
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch("adsops.hostctl.service.asyncssh.connect", return_value=mock_conn):
        from adsops.hostctl.service import probe_host

        result = probe_host("reachable-host.example.com")
        assert result["reachable"] is True
        assert result["error"] is None
        assert result["host"] == "reachable-host.example.com"


def test_probe_host_unreachable():
    """probe_host returns reachable=False when SSH connection fails."""
    with patch(
        "adsops.hostctl.service.asyncssh.connect",
        side_effect=ConnectionRefusedError("Connection refused"),
    ):
        from adsops.hostctl.service import probe_host

        result = probe_host("dead-host.example.com")
        assert result["reachable"] is False
        assert result["error"] is not None
        assert result["host"] == "dead-host.example.com"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_list_invokes_service(mock_db_session):
    """adsops hostctl list calls service.list_resources."""
    mock_db_session.scalars.return_value.all.return_value = []

    from adsops.hostctl.cli import app

    runner = CliRunner()
    with patch("adsops.hostctl.service.list_resources", return_value=[]) as mock_list:
        result = runner.invoke(app, ["list"])
        mock_list.assert_called_once()
    assert result.exit_code == 0


def test_cli_json_output(mock_db_session):
    """adsops hostctl list --json produces valid JSON with proto field names."""
    r = _make_resource(hostname="json-host.example.com", status="active")
    mock_db_session.scalars.return_value.all.return_value = [r]

    from adsops.hostctl.cli import app
    from adsops.hostctl.service import _to_proto

    proto_record = _to_proto(r)

    runner = CliRunner()
    with patch("adsops.hostctl.service.list_resources", return_value=[proto_record]):
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    # Output should be valid JSON
    output_text = result.output.strip()
    parsed = json.loads(output_text)
    assert "hostname" in parsed
    assert parsed["hostname"] == "json-host.example.com"


def test_cli_probe_command():
    """adsops hostctl probe calls service.probe_host and reports result."""
    from adsops.hostctl.cli import app

    runner = CliRunner()
    with patch(
        "adsops.hostctl.service.probe_host",
        return_value={"host": "myhost", "reachable": True, "error": None},
    ):
        result = runner.invoke(app, ["probe", "myhost"])
    assert result.exit_code == 0
    assert "reachable" in result.output


def test_cli_probe_command_unreachable():
    """adsops hostctl probe exits with code 1 when host is unreachable."""
    from adsops.hostctl.cli import app

    runner = CliRunner()
    with patch(
        "adsops.hostctl.service.probe_host",
        return_value={"host": "deadhost", "reachable": False, "error": "Connection refused"},
    ):
        result = runner.invoke(app, ["probe", "deadhost"])
    assert result.exit_code == 1
