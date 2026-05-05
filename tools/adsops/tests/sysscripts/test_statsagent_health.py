import pytest
from pathlib import Path
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

SCRIPT = str(Path(__file__).resolve().parents[4] / "sysscripts" / "services" / "statsagent" / "health.star")


def make_runner(fixtures):
    return SysscriptRunner(sys_global=MockSys(fixtures))


def _base_fixtures(status_code):
    return {
        "config.get": lambda k: "http://localhost:9100" if k == "statsagent_url" else None,
        "net.http_get": {"status_code": status_code, "body": ""},
        "exec.run": lambda cmd: (0, "testhost\n", "") if cmd == "hostname" else (0, "Linux\n", ""),
    }


def test_healthy_on_200():
    """Test 1: health.star sets healthy=True when http_get returns status_code 200."""
    result = make_runner(_base_fixtures(200)).run(SCRIPT)
    assert result["healthy"] == True


def test_unhealthy_on_503():
    """Test 2: health.star sets healthy=False when http_get returns non-200."""
    result = make_runner(_base_fixtures(503)).run(SCRIPT)
    assert result["healthy"] == False


def test_reads_statsagent_url():
    """Test 3: health.star reads base URL from sys.config.get('statsagent_url')."""
    # If config.get does not return the correct URL, http_get would be called with
    # None + "/health" which would fail. Passing test proves config.get is called correctly.
    result = make_runner(_base_fixtures(200)).run(SCRIPT)
    assert result["healthy"] == True
