"""JSON-line protocol for CLI <-> Daemon communication.

The envelope shapes live in ``models.py`` as Pydantic models; this module is
just the (de)serialization seam plus the ``ok_response`` / ``error_response``
constructors the command handlers call.
"""

from __future__ import annotations

import json

from .models import (
    ErrorResponse,
    OkResponse,
    Response,
    ResponseData,
    response_adapter,
)


def parse_command(line: str) -> dict[str, object]:
    """Parse a JSON-line command into a raw dict.

    Validation into a typed ``Command`` happens in ``commands.execute`` so a
    malformed command becomes a graceful error response rather than a crash.
    """
    return json.loads(line.strip())


def serialize_response(response: Response) -> bytes:
    """Serialize a response model to JSON-line bytes."""
    return response_adapter.dump_json(response, exclude_none=True) + b"\n"


def ok_response(
    id: str, data: ResponseData | dict[str, object] | None = None
) -> OkResponse:
    if data is None:
        return OkResponse(id=id)
    if isinstance(data, ResponseData):
        return OkResponse(id=id, data=data)
    return OkResponse(id=id, data=ResponseData.model_validate(data))


def error_response(id: str, error: str) -> ErrorResponse:
    return ErrorResponse(id=id, error=error)
