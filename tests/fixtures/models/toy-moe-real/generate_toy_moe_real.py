#!/usr/bin/env python3
"""Generates the toy-moe-real fixtures used to prove the router's selected
expert actually changes the forward's output, instead of the expert pager
only recording a "touch" for telemetry while every expert secretly shares
the same synthetic/base weights.

- toy-moe-real.safetensors: the base model, embedding.weight [4, 8]
  (one-hot on hidden dim 0 for "alpha", index 0) and a DECOY lm_head.weight
  [4, 8] whose column 0 argmaxes to "alpha" (index 0) -- this is what the
  output would be if the routed expert's real weight were NOT applied.
- expert0.safetensors / expert1.safetensors: real per-expert shards
  (moe_expert_shards in model.us4manifest). expert0's lm_head.weight
  column 0 argmaxes to "beta" (index 1) instead -- deliberately different
  from the base decoy, so observing "beta" in the generated output proves
  the runtime actually applied expert 0's real weight (the router's
  default top-1 pick for a prompt with no special keywords), not the
  base/decoy tensor.

Run manually to regenerate:
    python3 tests/fixtures/models/toy-moe-real/generate_toy_moe_real.py
"""
import json
import os
import struct

VOCAB = ["alpha", "beta", "gamma", "delta"]
HIDDEN_SIZE = 8


def write_safetensors(path, embedding_col0, lm_head_col0):
    embedding = [0.0] * (len(VOCAB) * HIDDEN_SIZE)
    if embedding_col0 is not None:
        for token, value in enumerate(embedding_col0):
            embedding[token * HIDDEN_SIZE + 0] = value

    lm_head = [0.0] * (len(VOCAB) * HIDDEN_SIZE)
    for token, value in enumerate(lm_head_col0):
        lm_head[token * HIDDEN_SIZE + 0] = value

    embedding_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
    lm_head_bytes = struct.pack(f"<{len(lm_head)}f", *lm_head)

    # lm_head's offset must reflect what actually gets written before it,
    # not the embedding buffer's size when the embedding tensor is skipped.
    embedding_bytes_written = embedding_bytes if embedding_col0 is not None else b""
    lm_head_start = len(embedding_bytes_written)

    header = {
        "lm_head.weight": {
            "dtype": "F32",
            "shape": [len(VOCAB), HIDDEN_SIZE],
            "data_offsets": [lm_head_start, lm_head_start + len(lm_head_bytes)],
        },
    }
    if embedding_col0 is not None:
        header["embedding.weight"] = {
            "dtype": "F32",
            "shape": [len(VOCAB), HIDDEN_SIZE],
            "data_offsets": [0, len(embedding_bytes)],
        }
    header_json = json.dumps(header).encode("utf-8")

    with open(path, "wb") as f:
        f.write(struct.pack("<Q", len(header_json)))
        f.write(header_json)
        f.write(embedding_bytes_written)
        f.write(lm_head_bytes)


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # "alpha" is one-hot on hidden 0; decoy lm_head argmaxes to "alpha".
    write_safetensors(
        os.path.join(out_dir, "toy-moe-real.safetensors"),
        embedding_col0=[1.0, 0.0, 0.0, 0.0],
        lm_head_col0=[5.0, 0.1, 0.2, 0.3],
    )
    # expert 0's real weight argmaxes to "beta" instead.
    write_safetensors(
        os.path.join(out_dir, "expert0.safetensors"),
        embedding_col0=None,
        lm_head_col0=[0.1, 5.0, 0.2, 0.3],
    )
    # expert 1 is unused by this test's default routing but present for a
    # genuine multi-shard manifest.
    write_safetensors(
        os.path.join(out_dir, "expert1.safetensors"),
        embedding_col0=None,
        lm_head_col0=[0.2, 0.1, 5.0, 0.3],
    )

    print("wrote toy-moe-real fixtures: base decoy argmaxes to 'alpha', "
          "expert0's real weight argmaxes to 'beta' -- observing 'beta' "
          "proves the router's selected expert weight was actually applied.")


if __name__ == "__main__":
    main()
