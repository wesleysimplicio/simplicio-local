"""Portable Simplicio Local inference data-plane primitives."""

from .daemon import InferenceDaemon
from .protocol import PROTOCOL_NAME, PROTOCOL_VERSION

__all__ = ["InferenceDaemon", "PROTOCOL_NAME", "PROTOCOL_VERSION"]
