import pytest
from adsops.sysscript.mock import MockSys, MockNamespace


def test_mocksys_import_path():
    """D-10: MockSys importable from adsops.sysscript.mock."""
    from adsops.sysscript.mock import MockSys
    assert MockSys is not None


def test_mocksys_fixture_return():
    """D-08: fixture data returned when namespace method called."""
    sys = MockSys({"net.http_get": "response body"})
    assert sys.net.http_get("https://example.com") == "response body"


def test_mocksys_callable_fixture():
    """D-08: callable fixtures receive args."""
    sys = MockSys({"exec.run": lambda cmd: (0, f"ran: {cmd}", "")})
    code, out, err = sys.exec.run("ls -la")
    assert code == 0
    assert "ran: ls -la" in out


def test_mocksys_missing_fixture_raises():
    """Missing fixture raises NotImplementedError with helpful message."""
    sys = MockSys({})
    with pytest.raises(NotImplementedError, match="no fixture for 'net.http_get'"):
        sys.net.http_get("url")


def test_mocksys_all_namespaces_exist():
    """D-09: all 14 sysscript.go namespaces + k3s stub exist."""
    sys = MockSys({})
    expected = [
        "net", "exec", "fs", "alerts", "security", "events",
        "packages", "containers", "config", "yaml", "json",
        "ini", "services", "proc", "k3s",
    ]
    for ns in expected:
        assert hasattr(sys, ns), f"Missing namespace: {ns}"
        assert isinstance(getattr(sys, ns), MockNamespace)


def test_mocksys_multiple_namespaces():
    """Multiple namespaces work independently."""
    sys = MockSys({
        "fs.read": "file content",
        "containers.run": {"id": "abc123"},
        "services.status": "running",
    })
    assert sys.fs.read("/etc/hosts") == "file content"
    assert sys.containers.run("nginx") == {"id": "abc123"}
    assert sys.services.status("nginx") == "running"


def test_mocksys_empty_fixtures():
    """MockSys with empty fixtures works (all calls raise NotImplementedError)."""
    sys = MockSys()
    with pytest.raises(NotImplementedError):
        sys.proc.list()
