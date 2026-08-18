"""Bounded binary value codec and versioned frame envelope.

The private Local protocol deliberately does not use JSON-RPC.  Values are
encoded using a small tagged binary format and are wrapped in an envelope with
length and CRC checks.  The codec is deterministic so golden vectors can be
shared by implementations in other languages.
"""

from __future__ import annotations

import io
import struct
import zlib
from typing import BinaryIO, Any

MAGIC = b"SLV2"
VERSION = 2
HEADER = struct.Struct("!4sBBHQII")
MAX_FRAME_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32
MAX_ITEMS = 100_000

REQUEST = 1
RESPONSE = 2
EVENT = 3
ERROR = 4


class FrameError(ValueError):
    """Raised for malformed, oversized, or incompatible frames."""


def _pack_text(value: str) -> bytes:
    data = value.encode("utf-8")
    if len(data) > MAX_FRAME_BYTES:
        raise FrameError("text value exceeds frame limit")
    return b"S" + struct.pack("!I", len(data)) + data


def encode_value(value: Any, *, _depth: int = 0) -> bytes:
    """Encode supported primitive/container values deterministically."""

    if _depth > MAX_DEPTH:
        raise FrameError("value nesting exceeds limit")
    if value is None:
        return b"N"
    if value is False:
        return b"F"
    if value is True:
        return b"T"
    if isinstance(value, int) and not isinstance(value, bool):
        return b"I" + struct.pack("!q", value)
    if isinstance(value, float):
        return b"D" + struct.pack("!d", value)
    if isinstance(value, str):
        return _pack_text(value)
    if isinstance(value, bytes):
        if len(value) > MAX_FRAME_BYTES:
            raise FrameError("byte value exceeds frame limit")
        return b"B" + struct.pack("!I", len(value)) + value
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ITEMS:
            raise FrameError("list exceeds item limit")
        return b"L" + struct.pack("!I", len(value)) + b"".join(
            encode_value(item, _depth=_depth + 1) for item in value
        )
    if isinstance(value, dict):
        if len(value) > MAX_ITEMS or not all(isinstance(k, str) for k in value):
            raise FrameError("map exceeds item limit or has a non-text key")
        encoded = [
            _pack_text(key) + encode_value(value[key], _depth=_depth + 1)
            for key in sorted(value)
        ]
        return b"M" + struct.pack("!I", len(encoded)) + b"".join(encoded)
    raise FrameError(f"unsupported value type: {type(value).__name__}")


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.items = 0

    def take(self, count: int) -> bytes:
        if count < 0 or self.offset + count > len(self.data):
            raise FrameError("truncated value")
        value = self.data[self.offset : self.offset + count]
        self.offset += count
        return value

    def u32(self) -> int:
        return struct.unpack("!I", self.take(4))[0]

    def text(self) -> str:
        size = self.u32()
        if size > MAX_FRAME_BYTES:
            raise FrameError("text value exceeds frame limit")
        try:
            return self.take(size).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FrameError("invalid UTF-8 text") from exc

    def value(self, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise FrameError("value nesting exceeds limit")
        self.items += 1
        if self.items > MAX_ITEMS:
            raise FrameError("value item limit exceeded")
        tag = self.take(1)
        if tag == b"N":
            return None
        if tag == b"F":
            return False
        if tag == b"T":
            return True
        if tag == b"I":
            return struct.unpack("!q", self.take(8))[0]
        if tag == b"D":
            return struct.unpack("!d", self.take(8))[0]
        if tag == b"S":
            return self.text()
        if tag == b"B":
            size = self.u32()
            if size > MAX_FRAME_BYTES:
                raise FrameError("byte value exceeds frame limit")
            return self.take(size)
        if tag == b"L":
            count = self.u32()
            if count > MAX_ITEMS:
                raise FrameError("list exceeds item limit")
            return [self.value(depth + 1) for _ in range(count)]
        if tag == b"M":
            count = self.u32()
            if count > MAX_ITEMS:
                raise FrameError("map exceeds item limit")
            result: dict[str, Any] = {}
            for _ in range(count):
                if self.take(1) != b"S":
                    raise FrameError("map key is not text")
                key = self.text()
                if key in result:
                    raise FrameError("duplicate map key")
                result[key] = self.value(depth + 1)
            return result
        raise FrameError(f"unknown value tag: {tag!r}")


def decode_value(data: bytes) -> Any:
    reader = _Reader(data)
    value = reader.value()
    if reader.offset != len(data):
        raise FrameError("trailing bytes after value")
    return value


def encode_frame(kind: int, request_id: int, payload: Any) -> bytes:
    body = encode_value(payload)
    if len(body) > MAX_FRAME_BYTES:
        raise FrameError("frame exceeds maximum size")
    checksum = zlib.crc32(body) & 0xFFFFFFFF
    return HEADER.pack(MAGIC, VERSION, kind, 0, request_id, len(body), checksum) + body


def decode_frame(data: bytes) -> tuple[int, int, Any]:
    if len(data) < HEADER.size:
        raise FrameError("truncated frame header")
    magic, version, kind, flags, request_id, size, checksum = HEADER.unpack(
        data[: HEADER.size]
    )
    if magic != MAGIC or version != VERSION or flags != 0:
        raise FrameError("unsupported frame header")
    if size > MAX_FRAME_BYTES or len(data) != HEADER.size + size:
        raise FrameError("invalid frame length")
    body = data[HEADER.size :]
    if zlib.crc32(body) & 0xFFFFFFFF != checksum:
        raise FrameError("frame checksum mismatch")
    return kind, request_id, decode_value(body)


def read_frame(stream: BinaryIO) -> tuple[int, int, Any] | None:
    header = stream.read(HEADER.size)
    if not header:
        return None
    if len(header) != HEADER.size:
        raise FrameError("truncated frame header")
    magic, version, kind, flags, request_id, size, checksum = HEADER.unpack(header)
    if magic != MAGIC or version != VERSION or flags != 0:
        raise FrameError("unsupported frame header")
    if size > MAX_FRAME_BYTES:
        raise FrameError("frame exceeds maximum size")
    body = stream.read(size)
    if len(body) != size:
        raise FrameError("truncated frame body")
    if zlib.crc32(body) & 0xFFFFFFFF != checksum:
        raise FrameError("frame checksum mismatch")
    return kind, request_id, decode_value(body)


def write_frame(stream: BinaryIO, kind: int, request_id: int, payload: Any) -> None:
    stream.write(encode_frame(kind, request_id, payload))
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()


def golden_vector() -> str:
    """Return a stable hex vector used by cross-language conformance tests."""

    return encode_frame(
        REQUEST,
        7,
        {"method": "handshake", "ok": True, "limits": [1, 2, 3]},
    ).hex()
