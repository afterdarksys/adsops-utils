import pathlib
import pytest
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

# Resolve path to lib/host.star relative to this test file.
# tests/sysscripts/ is 2 dirs below tools/adsops/, and sysscripts/ is at the repo root.
# __file__ -> tools/adsops/tests/sysscripts/test_host_star.py
# parents[0] = tests/sysscripts/
# parents[1] = tests/
# parents[2] = tools/adsops/
# parents[3] = tools/
# parents[4] = repo root
SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "sysscripts" / "lib" / "host.star"


def _exec_fixture(cmd):
    if cmd == "hostname":
        return (0, "testhost\n", "")
    if cmd == "uname -s":
        return (0, "Linux\n", "")
    if cmd == "uptime":
        return (0, " 10:30:00 up 5 days,  3:22,  1 user", "")
    return (1, "", "unknown command")


def _make_runner(fixtures=None):
    if fixtures is None:
        fixtures = {"exec.run": _exec_fixture}
    return SysscriptRunner(sys_global=MockSys(fixtures))


def test_host_info_hostname(tmp_path):
    """Test 1: host_info() returns dict with 'hostname' key from sys.exec.run('hostname')."""
    runner = _make_runner()
    result = runner.run(str(SCRIPT))
    info = result["host_info"]()
    assert info["hostname"] == "testhost"


def test_host_info_os(tmp_path):
    """Test 2: host_info() returns dict with 'os' key from sys.exec.run('uname -s')."""
    runner = _make_runner()
    result = runner.run(str(SCRIPT))
    info = result["host_info"]()
    assert info["os"] == "Linux"


def test_host_info_unknown_on_error(tmp_path):
    """Test 3: host_info() returns 'unknown' for hostname when exec.run returns non-zero."""
    def error_fixture(cmd):
        return (1, "", "error")

    runner = _make_runner({"exec.run": error_fixture})
    result = runner.run(str(SCRIPT))
    info = result["host_info"]()
    assert info["hostname"] == "unknown"


def test_host_uptime(tmp_path):
    """Test 4: host_uptime() returns uptime string from sys.exec.run('uptime')."""
    runner = _make_runner()
    result = runner.run(str(SCRIPT))
    uptime = result["host_uptime"]()
    assert "up 5 days" in uptime
