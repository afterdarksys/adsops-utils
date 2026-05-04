import typer
from typing import Annotated

app = typer.Typer(help="System stats collection", no_args_is_help=True)


@app.command("once")
def stats_once(
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
):
    """Collect local system metrics once."""
    from adsops.stats.local import collect_once
    from adsops.output import print_proto

    snap = collect_once()
    fmt = "json" if json_out else ("proto" if proto_out else "text")
    print_proto(snap, fmt)


@app.command("fetch")
def stats_fetch(
    host: str = typer.Argument(..., help="Statsagent host to fetch from"),
    port: int = typer.Option(9100, help="Statsagent port"),
    json_out: Annotated[bool, typer.Option("--json")] = False,
    proto_out: Annotated[bool, typer.Option("--proto")] = False,
):
    """Fetch stats from remote statsagent endpoint."""
    from adsops.stats.remote import fetch_once
    from adsops.output import print_proto

    payload = fetch_once(host, port)
    fmt = "json" if json_out else ("proto" if proto_out else "text")
    print_proto(payload, fmt)
