#!/usr/bin/env python3
"""Create reproducible int8/int4 fuzz seeds from real safetensors weights.

The repository intentionally does not commit generated binary corpora. This
script derives them from a checked-in real-weight fixture (or a user-supplied
production checkpoint), records the source hash, and keeps synthetic edge cases
alongside the real quantized blocks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path


def read_f32_values(path: Path) -> list[float]:
    raw = path.read_bytes()
    if len(raw) < 8:
        raise ValueError(f"not a safetensors file: {path}")
    header_size = struct.unpack_from("<Q", raw, 0)[0]
    header_end = 8 + header_size
    header = json.loads(raw[8:header_end])
    values: list[float] = []
    for name, tensor in header.items():
        if name == "__metadata__":
            continue
        dtype = tensor.get("dtype")
        if dtype not in {"F32", "F16", "BF16"}:
            continue
        start, end = tensor["data_offsets"]
        payload = raw[header_end + start : header_end + end]
        if dtype == "F32":
            values.extend(struct.unpack(f"<{len(payload) // 4}f", payload))
        elif dtype == "F16":
            values.extend(float(x) for x in struct.unpack(
                f"<{len(payload) // 2}e", payload))
        else:
            for (word,) in struct.iter_unpack("<H", payload):
                values.append(struct.unpack("<f", struct.pack("<I", word << 16))[0])
    if not values:
        raise ValueError(f"no F32/F16/BF16 tensors in {path}")
    return values


def quantize(values: list[float], bits: int, group_size: int = 32) -> bytes:
    maximum = 127 if bits == 8 else 7
    encoded = bytearray((len(values) + (1 if bits == 4 else 0)) // (2 if bits == 4 else 1))
    for begin in range(0, len(values), group_size):
        group = values[begin : begin + group_size]
        scale = max((abs(x) for x in group if math.isfinite(x)), default=0.0)
        scale = scale / maximum if scale > 1e-12 else 1.0
        for offset, value in enumerate(group):
            quantized = max(-maximum if bits == 8 else -8,
                            min(maximum, round(value / scale)))
            if bits == 8:
                encoded[begin + offset] = quantized & 0xFF
            else:
                nibble = quantized & 0x0F
                index = (begin + offset) // 2
                if (begin + offset) % 2:
                    encoded[index] = (encoded[index] & 0x0F) | (nibble << 4)
                else:
                    encoded[index] = (encoded[index] & 0xF0) | nibble
    return bytes(encoded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("tests/fixtures/engine/colibri/glm_tiny/model.safetensors"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("runtime/fuzz/corpus")
    )
    args = parser.parse_args()
    values = read_f32_values(args.source)
    args.output.mkdir(parents=True, exist_ok=True)
    int8_dir = args.output / "dequant_int8"
    int4_dir = args.output / "dequant_int4"
    int8_dir.mkdir(exist_ok=True)
    int4_dir.mkdir(exist_ok=True)
    # Multiple overlapping slices retain distributions from different real
    # tensors while keeping startup deterministic and the corpus small.
    block = 256
    count = min(100, max(1, (len(values) - block) // block + 1))
    for index in range(count):
        start = (index * block) % max(1, len(values) - block + 1)
        chunk = values[start : start + block]
        (int8_dir / f"real-{index:03d}").write_bytes(quantize(chunk, 8))
        (int4_dir / f"real-{index:03d}").write_bytes(quantize(chunk, 4))
    (int8_dir / "edge-zero").write_bytes(bytes(128))
    (int8_dir / "edge-max").write_bytes(bytes([0x7F, 0x80]) * 64)
    (int4_dir / "edge-zero").write_bytes(bytes(128))
    (int4_dir / "edge-nibbles").write_bytes(bytes([0x87, 0xF0, 0x08, 0x7F]) * 32)
    manifest = {
        "source": str(args.source),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "values": len(values),
        "real_seed_count": count,
        "group_size": 32,
        "note": "real-weight-derived quantized blocks plus deterministic edge cases",
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
