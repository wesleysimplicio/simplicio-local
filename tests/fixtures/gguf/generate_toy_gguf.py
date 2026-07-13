#!/usr/bin/env python3
"""Generates a genuine minimal .gguf fixture (real binary container, real
float32 tensor bytes) for gguf_reader_contract_test.cpp.

The GGUF format is: a 4-byte magic "GGUF", a uint32 version, a uint64 tensor
count, a uint64 metadata key-value count, that many metadata entries (each a
length-prefixed string key + typed value), then that many tensor info entries
(length-prefixed string name + uint32 dimension count + that many uint64
dims + uint32 ggml_type + uint64 byte offset relative to the tensor data
section), then padding up to `general.alignment` (or 32 by default), then
the raw tensor bytes themselves in the order the tensor infos were written.
This script writes that format directly (no external gguf dependency
needed) so the fixture is a real, spec-compliant file instead of a text
placeholder.

Run manually to regenerate:
    python3 tests/fixtures/gguf/generate_toy_gguf.py
"""
import os
import struct

GGML_TYPE_F32 = 0
ALIGNMENT = 32

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


def pack_string(text):
    encoded = text.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def pack_tensor_info(name, shape, ggml_type, offset):
    out = pack_string(name)
    out += struct.pack("<I", len(shape))
    for dim in shape:
        out += struct.pack("<Q", dim)
    out += struct.pack("<I", ggml_type)
    out += struct.pack("<Q", offset)
    return out


def main():
    embedding_bytes = struct.pack(f"<{len(EMBEDDING_VALUES)}f", *EMBEDDING_VALUES)
    lm_head_bytes = struct.pack(f"<{len(LM_HEAD_VALUES)}f", *LM_HEAD_VALUES)

    header = struct.pack("<4sIQQ", b"GGUF", 3, 2, 0)  # magic, version, tensor_count, kv_count

    tensor_infos = pack_tensor_info(
        "embedding.weight", EMBEDDING_SHAPE, GGML_TYPE_F32, 0
    )
    tensor_infos += pack_tensor_info(
        "lm_head.weight", LM_HEAD_SHAPE, GGML_TYPE_F32, len(embedding_bytes)
    )

    body_before_data = header + tensor_infos
    padding = (-len(body_before_data)) % ALIGNMENT

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "toy_real.gguf")
    with open(out_path, "wb") as f:
        f.write(body_before_data)
        f.write(b"\x00" * padding)
        f.write(embedding_bytes)
        f.write(lm_head_bytes)

    print(f"wrote {out_path}: {len(body_before_data)}-byte header+tensor-info, "
          f"{padding} bytes padding, "
          f"{len(embedding_bytes) + len(lm_head_bytes)} bytes of tensor data")


if __name__ == "__main__":
    main()
