import asyncio
import aiohttp
from google.protobuf.json_format import Parse
from adsops.v1 import telemetry_pb2


async def _fetch(host: str, port: int = 9100) -> telemetry_pb2.TelemetryPayload:
    """Async fetch from statsagent /stats endpoint.

    T-02-09 mitigations:
    - Parse response via protobuf json_format.Parse which validates field types
    - aiohttp timeout=10s prevents hung connections
    """
    url = f"http://{host}:{port}/stats"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            body = await resp.text()
            return Parse(body, telemetry_pb2.TelemetryPayload())


def fetch_once(host: str, port: int = 9100) -> telemetry_pb2.TelemetryPayload:
    """Sync wrapper for CLI (D-06). Fetch stats from remote statsagent endpoint."""
    return asyncio.run(_fetch(host, port))
