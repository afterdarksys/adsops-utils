import pathlib
import pytest
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

# Resolve path to lib/docker.star from test file location.
# parents[4] = repo root
SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "sysscripts" / "lib" / "docker.star"


def _make_runner(fixtures):
    return SysscriptRunner(sys_global=MockSys(fixtures))


def test_container_list_returns_list():
    """Test 1: container_list() returns list from sys.containers.list()."""
    containers = [{"id": "abc", "name": "nginx", "state": "running"}]
    runner = _make_runner({"containers.list": containers})
    result = runner.run(str(SCRIPT))
    listed = result["container_list"]()
    assert listed == containers


def test_container_stats_returns_dict():
    """Test 2: container_stats(name) returns stats dict from sys.containers.stats(name)."""
    runner = _make_runner({
        "containers.stats": lambda name: {"cpu_pct": 5.2, "name": name},
    })
    result = runner.run(str(SCRIPT))
    stats = result["container_stats"]("nginx")
    assert stats["cpu_pct"] == 5.2
    assert stats["name"] == "nginx"


def test_container_list_empty():
    """Test 3: container_list() with empty list returns empty list."""
    runner = _make_runner({"containers.list": []})
    result = runner.run(str(SCRIPT))
    listed = result["container_list"]()
    assert listed == []
