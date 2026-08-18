"""Versioned protocol names and request/response helpers."""

from __future__ import annotations

PROTOCOL_NAME = "simplicio.inference-backend/v2"
PROTOCOL_VERSION = 2
METHODS = (
    "handshake",
    "capabilities",
    "estimate",
    "load",
    "warm",
    "generate",
    "cancel",
    "status",
    "drain",
    "unload",
    "shutdown",
)


class ProtocolError(ValueError):
    """A client-visible protocol error."""


def ok(method: str, **values: object) -> dict[str, object]:
    return {"ok": True, "method": method, **values}


def error(method: str, code: str, message: str, **values: object) -> dict[str, object]:
    return {"ok": False, "method": method, "error": {"code": code, "message": message}, **values}
