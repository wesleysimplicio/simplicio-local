#!/usr/bin/env python3
"""Generates a genuine minimal .safetensors fixture (real binary format, real
float32 tensor bytes) for safetensors_reader_contract_test.cpp.

The safetensors format is: an 8-byte little-endian header length N, then N
bytes of UTF-8 JSON describing each tensor's dtype/shape/byte offsets into
the section that immediately follows, then the raw tensor bytes themselves.
This script writes that format directly (no external safetensors dependency
needed) so the fixture is a real, spec-compliant file instead of a text
placeholder.

Run manually to regenerate:
    python3 tests/fixtures/safetensors/generate_toy_safetensors.py
"""
import json
import os
import struct

EMBEDDING_SHAPE = (4, 3)
EMBEDDING_VALUES = [
    0.1, 0.2, 0.3,
    1.1, 1.2, 1.3,
    2.1, 2.2, 2.3,
    3.1, 3.2, 3.3,
]

LM_HEAD_SHAPE = (3, 4)
LM_HEAD_VALUES = [
    0.5, -0.5, 1.5, -1.5,
    0.25, -0.25, 0.75, -0.75,
    2.0, -2.0, 3.0, -3.0,
]


def main():
    embedding_bytes = struct.pack(f"<{len(EMBEDDING_VALUES)}f", *EMBEDDING_VALUES)
    lm_head_bytes = struct.pack(f"<{len(LM_HEAD_VALUES)}f", *LM_HEAD_VALUES)

    header = {
        "embedding.weight": {
            "dtype": "F32",
            "shape": list(EMBEDDING_SHAPE),
            "data_offsets": [0, len(embedding_bytes)],
        },
        "lm_head.weight": {
            "dtype": "F32",
            "shape": list(LM_HEAD_SHAPE),
            "data_offsets": [len(embedding_bytes),
                             len(embedding_bytes) + len(lm_head_bytes)],
        },
    }
    header_json = json.dumps(header).encode("utf-8")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "toy_real.safetensors")
    with open(out_path, "wb") as f:
        f.write(struct.pack("<Q", len(header_json)))
        f.write(header_json)
        f.write(embedding_bytes)
        f.write(lm_head_bytes)

    print(f"wrote {out_path}: {len(header_json)}-byte header, "
          f"{len(embedding_bytes) + len(lm_head_bytes)} bytes of tensor data")


if __name__ == "__main__":
    main()
