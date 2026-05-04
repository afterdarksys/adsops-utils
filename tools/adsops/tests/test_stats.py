import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.protobuf.json_format import MessageToJson

from adsops.v1 import stats_pb2, telemetry_pb2


# ---------------------------------------------------------------------------
# Local stats tests (real psutil — no mock needed for local collection)
# ---------------------------------------------------------------------------

def test_collect_once_returns_snapshot():
    """collect_once() returns a StatsSnapshot with non-zero cpu_cores and mem_total_bytes."""
    from adsops.stats.local import collect_once

    snap = collect_once()
    assert isinstance(snap, stats_pb2.StatsSnapshot)
    assert snap.system.cpu_cores > 0
    assert snap.system.mem_total_bytes > 0


def test_collect_once_has_hostname():
    """snap.system.hostname is not empty."""
    from adsops.stats.local import collect_once

    snap = collect_once()
    assert snap.system.hostname != ""


def test_collect_once_json_output():
    """MessageToJson(collect_once()) produces valid JSON."""
    from adsops.stats.local import collect_once

    snap = collect_once()
    json_str = MessageToJson(snap)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    assert "system" in parsed


# ---------------------------------------------------------------------------
# Remote fetch test — mocked aiohttp
# ---------------------------------------------------------------------------

def test_fetch_once_parses_response():
    """fetch_once() returns a TelemetryPayload parsed from mocked JSON response."""
    sample_json = '{"hostId": "test-host", "timestamp": 1234567890}'

    # Build the async context manager mock for aiohttp.ClientSession and response
    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = AsyncMock(return_value=sample_json)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        from adsops.stats.remote import fetch_once
        payload = fetch_once("somehost", 9100)

    assert isinstance(payload, telemetry_pb2.TelemetryPayload)
    assert payload.host_id == "test-host"


# ---------------------------------------------------------------------------
# CLI stats once test
# ---------------------------------------------------------------------------

def test_stats_cli_once():
    """Invoking `stats once --json` via CliRunner produces JSON output with 'system'."""
    from typer.testing import CliRunner
    from adsops.stats.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["once", "--json"])
    assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
    parsed = json.loads(result.output)
    assert "system" in parsed
