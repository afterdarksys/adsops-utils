from typing import Any, Callable, Optional


class MockNamespace:
    """Fixture-backed namespace that returns canned responses."""

    def __init__(self, name: str, fixtures: dict[str, Any]):
        self._name = name
        self._fixtures = fixtures

    def __getattr__(self, method: str) -> Callable:
        key = f"{self._name}.{method}"

        def _handler(*args, **kwargs):
            fixture = self._fixtures.get(key)
            if fixture is None:
                raise NotImplementedError(
                    f"MockSys: no fixture for '{key}'. "
                    f"Pass fixtures={{'{key}': <return_value>}} to MockSys()"
                )
            return fixture(*args, **kwargs) if callable(fixture) else fixture

        return _handler


class MockSys:
    """
    Drop-in replacement for the Starlark sys global (D-10).
    Tests instantiate with fixture dict keyed by "namespace.method".
    Values are return values or callables.

    Usage:
        sys = MockSys({"net.http_get": "OK", "exec.run": lambda cmd: (0, "out", "")})
        result = sys.net.http_get("https://example.com")  # returns "OK"
    """

    def __init__(self, fixtures: Optional[dict[str, Any]] = None):
        fixtures = fixtures or {}
        # All 14 namespaces from sysscript.go (VERIFIED) + k3s stub for Phase 3
        self.net = MockNamespace("net", fixtures)
        self.exec = MockNamespace("exec", fixtures)
        self.fs = MockNamespace("fs", fixtures)
        self.alerts = MockNamespace("alerts", fixtures)
        self.security = MockNamespace("security", fixtures)
        self.events = MockNamespace("events", fixtures)
        self.packages = MockNamespace("packages", fixtures)
        self.containers = MockNamespace("containers", fixtures)
        self.config = MockNamespace("config", fixtures)
        self.yaml = MockNamespace("yaml", fixtures)
        self.json = MockNamespace("json", fixtures)
        self.ini = MockNamespace("ini", fixtures)
        self.services = MockNamespace("services", fixtures)
        self.proc = MockNamespace("proc", fixtures)
        self.k3s = MockNamespace("k3s", fixtures)  # Phase 3 forward-compat stub
