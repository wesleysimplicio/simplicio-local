#!/usr/bin/env python3
"""Generates the toy-llama-real fixture used to prove that LlamaAdapter's
NEON/GQA-specific BuildQueryRow/BuildKeyRow/BuildValueRow path actually uses
real embedding/lm_head weights when they're available (issue #81.4b),
instead of unconditionally calling BuildTokenEmbedding without ever passing
the asset through.

hidden_size=4, query_heads=1, kv_heads=1, head_dim=4 (kv width == hidden
size) so the SAME embedding.weight tensor is shape-compatible for the
query row, the key row, and the value row.

- embedding.weight [4, 4]: row "alpha" (index 0, the manifest's
  default_prompt_token) is one-hot on hidden dim 0. With a single-token
  prompt and maxTokens=1, RoPE at position 0 is the identity rotation, so
  the query row and the lone key/value row are exactly this one-hot
  vector -- attention over a single key/value pair is trivially that
  vector, so the context vector is deterministic and known ahead of time.
- lm_head.weight [4, 4]: column 0 argmaxes to "beta" (index 1). Since the
  context vector is one-hot on dim 0, the output logit for each
  vocabulary token is exactly that token's lm_head column-0 value, so the
  external oracle prediction for this fixture is "beta".

Run manually to regenerate:
    python3 tests/fixtures/models/toy-llama-real/generate_toy_llama_real.py
"""
import json
import os
import struct

VOCAB = ["alpha", "beta", "gamma", "delta"]
HIDDEN_SIZE = 4

EMBEDDING_ROWS = [
    [1.0, 0.0, 0.0, 0.0],  # alpha
    [0.0, 1.0, 0.0, 0.0],  # beta
    [0.0, 0.0, 1.0, 0.0],  # gamma
    [0.0, 0.0, 0.0, 1.0],  # delta
]

LM_HEAD_COL0 = [0.1, 5.0, 0.2, 0.3]  # argmaxes to "beta" (index 1)


def main():
    embedding = [value for row in EMBEDDING_ROWS for value in row]

    lm_head = [0.0] * (len(VOCAB) * HIDDEN_SIZE)
    for token, value in enumerate(LM_HEAD_COL0):
        lm_head[token * HIDDEN_SIZE + 0] = value

    embedding_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
    lm_head_bytes = struct.pack(f"<{len(lm_head)}f", *lm_head)

    header = {
        "embedding.weight": {
            "dtype": "F32",
            "shape": [len(VOCAB), HIDDEN_SIZE],
            "data_offsets": [0, len(embedding_bytes)],
        },
        "lm_head.weight": {
            "dtype": "F32",
            "shape": [len(VOCAB), HIDDEN_SIZE],
            "data_offsets": [len(embedding_bytes),
                             len(embedding_bytes) + len(lm_head_bytes)],
        },
    }
    header_json = json.dumps(header).encode("utf-8")

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "toy-llama-real.safetensors")
    with open(out_path, "wb") as f:
        f.write(struct.pack("<Q", len(header_json)))
        f.write(header_json)
        f.write(embedding_bytes)
        f.write(lm_head_bytes)

    print(f"wrote {out_path}: base embedding is one-hot per vocabulary row, "
          f"lm_head column 0 argmaxes to 'beta' -- observing 'beta' with "
          f"maxTokens=1 proves the real weights drove the output.")


if __name__ == "__main__":
    main()
