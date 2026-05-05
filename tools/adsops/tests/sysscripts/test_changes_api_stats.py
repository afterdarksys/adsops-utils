import pytest
from pathlib import Path
from adsops.sysscript.mock import MockSys
from adsops.sysscript.runner import SysscriptRunner

SCRIPT = str(Path(__file__).resolve().parents[4] / "sysscripts" / "services" / "changes-api" / "stats.star")

PROMETHEUS_BODY = (
    "# HELP http_requests_total The total number of HTTP requests.\n"
    "# TYPE http_requests_total counter\n"
    'http_requests_total{method="GET",code="200"} 1234\n'
    "# HELP http_request_duration_seconds HTTP request duration.\n"
    "# TYPE http_request_duration_seconds histogram\n"
    "http_request_duration_seconds_sum 45.6\n"
    "http_request_duration_seconds_count 1234\n"
)


def make_runner(body):
    return SysscriptRunner(sys_global=MockSys({
        "config.get": lambda k: "http://localhost:8080" if k == "changes_api_url" else None,
        "net.http_get": {"status_code": 200, "body": body},
        "exec.run": lambda cmd: (0, "testhost\n", "") if cmd == "hostname" else (0, "Linux\n", ""),
    }))


def test_parses_request_count():
    """Test 1: stats.star sets request_count from Prometheus body."""
    result = make_runner(PROMETHEUS_BODY).run(SCRIPT)
    assert result["request_count"] == "1234"


def test_parses_latency_sum_and_count():
    """Test 2: stats.star sets latency_sum and latency_count from Prometheus histogram lines."""
    result = make_runner(PROMETHEUS_BODY).run(SCRIPT)
    assert result["latency_sum"] == "45.6"
    assert result["latency_count"] == "1234"


def test_computes_latency_avg():
    """Test 3: stats.star computes latency_avg when sum and count are available."""
    result = make_runner(PROMETHEUS_BODY).run(SCRIPT)
    assert abs(result["latency_avg"] - (45.6 / 1234)) < 0.001


def test_empty_body_returns_none():
    """Test 4: stats.star handles empty metrics body gracefully (request_count remains None)."""
    result = make_runner("").run(SCRIPT)
    assert result["request_count"] is None


def test_reads_config_url():
    """Test 5: stats.star reads base URL from sys.config.get('changes_api_url') per D-10."""
    # If config.get does not return the correct URL, http_get would be called with
    # None + "/metrics" which would fail. Passing test proves config.get is called correctly.
    result = make_runner(PROMETHEUS_BODY).run(SCRIPT)
    assert result["request_count"] is not None
