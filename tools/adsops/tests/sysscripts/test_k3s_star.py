import pathlib
import pytest
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

# Resolve path to lib/k3s.star from test file location.
# parents[4] = repo root
SCRIPT = pathlib.Path(__file__).resolve().parents[4] / "sysscripts" / "lib" / "k3s.star"


def _make_runner(fixtures):
    return SysscriptRunner(sys_global=MockSys(fixtures))


def test_k3s_node_list_returns_list():
    """Test 1: k3s_node_list() returns list from sys.k3s.nodes()."""
    nodes = [{"name": "node1", "ready": True}]
    runner = _make_runner({"k3s.nodes": nodes})
    result = runner.run(str(SCRIPT))
    listed = result["k3s_node_list"]()
    assert listed == nodes


def test_k3s_pod_list_returns_list():
    """Test 2: k3s_pod_list() returns list from sys.k3s.pods()."""
    pods = [{"name": "pod1", "namespace": "default"}]
    runner = _make_runner({"k3s.pods": lambda *a: [{"name": "pod1", "namespace": a[0] if a else "default"}]})
    result = runner.run(str(SCRIPT))
    listed = result["k3s_pod_list"]()
    assert listed == pods


def test_k3s_pod_list_with_namespace():
    """Test 3: k3s_pod_list(namespace) passes namespace through to sys.k3s.pods(namespace)."""
    runner = _make_runner({
        "k3s.pods": lambda *a: [{"name": "pod1", "namespace": a[0] if a else "default"}],
    })
    result = runner.run(str(SCRIPT))
    listed = result["k3s_pod_list"]("kube-system")
    assert listed[0]["namespace"] == "kube-system"
