import sys
from typing import Any

from google.protobuf.json_format import MessageToJson, MessageToDict
from google.protobuf.message import Message
from rich.console import Console
from rich.table import Table

console = Console()


def _proto_to_text(msg: Message) -> str:
    """Render a proto message as a human-readable key=value string."""
    fields = MessageToDict(msg, preserving_proto_field_name=True)
    lines = []
    for k, v in fields.items():
        if isinstance(v, (list, dict)):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines) if lines else str(msg)


def format_output(msg: Message, fmt: str = "text") -> "str | bytes":
    """Format a proto message as text, JSON, or binary proto."""
    if fmt == "json":
        return MessageToJson(msg)
    elif fmt == "proto":
        return msg.SerializeToString()
    else:
        return _proto_to_text(msg)


def print_proto(msg: Message, fmt: str = "text") -> None:
    """Print a proto message in the requested format."""
    if fmt == "proto":
        sys.stdout.buffer.write(msg.SerializeToString())
    else:
        print(format_output(msg, fmt))


def print_protos(msgs: list, fmt: str = "text") -> None:
    """Print a list of proto messages in the requested format."""
    for msg in msgs:
        print_proto(msg, fmt)
