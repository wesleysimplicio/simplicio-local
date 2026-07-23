#!/usr/bin/env python3
"""Split one safetensors file into deterministic, dependency-free shards."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def read_source(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    if len(raw) < 8:
        raise ValueError("safetensors file is shorter than its length prefix")
    header_len = struct.unpack_from("<Q", raw)[0]
    data_start = 8 + header_len
    if data_start > len(raw):
        raise ValueError("safetensors header extends beyond the file")
    return json.loads(raw[8:data_start]), raw[data_start:]


def encoded_shard(entries: list[tuple[str, dict, bytes]], metadata: object) -> bytes:
    header: dict[str, object] = {}
    if metadata is not None:
        header["__metadata__"] = metadata
    offset = 0
    payload = bytearray()
    for name, spec, tensor_data in entries:
        item = {key: value for key, value in spec.items() if key != "data_offsets"}
        item["data_offsets"] = [offset, offset + len(tensor_data)]
        header[name] = item
        payload.extend(tensor_data)
        offset += len(tensor_data)
    header_bytes = json.dumps(
        header, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    header_bytes += b" " * ((8 - len(header_bytes) % 8) % 8)
    return struct.pack("<Q", len(header_bytes)) + header_bytes + payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-data-bytes", type=int, default=400_000)
    parser.add_argument("--prefix", default="model")
    args = parser.parse_args()
    if args.max_data_bytes <= 0:
        parser.error("--max-data-bytes must be positive")

    header, data = read_source(args.source)
    metadata = header.get("__metadata__")
    groups: list[list[tuple[str, dict, bytes]]] = [[]]
    group_bytes = 0
    for name, spec in header.items():
        if name == "__metadata__":
            continue
        begin, end = spec["data_offsets"]
        if not (0 <= begin <= end <= len(data)):
            raise ValueError(f"invalid data_offsets for {name}")
        tensor_data = data[begin:end]
        if groups[-1] and group_bytes + len(tensor_data) > args.max_data_bytes:
            groups.append([])
            group_bytes = 0
        groups[-1].append((name, spec, tensor_data))
        group_bytes += len(tensor_data)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    count = len(groups)
    for index, entries in enumerate(groups, 1):
        target = args.output_dir / f"{args.prefix}-{index:05d}-of-{count:05d}.safetensors"
        target.write_bytes(encoded_shard(entries, metadata))
        print(f"{target}: {target.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
