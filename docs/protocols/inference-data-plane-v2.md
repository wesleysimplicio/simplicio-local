# Inference Data Plane v2 — delivery matrix

The Local owns physical model and device work. Runtime policy, tool execution,
workspace effects and final task completion remain outside this repository. The
private contract is `simplicio.inference-backend/v2`, with binary typed frames,
bounded lifecycle and `effect_authority=none`.

## Delivery matrix

| Issue | Delivered surface | Local evidence | Promotion boundary |
|---:|---|---|---|
| #191 | persistent daemon, binary framing, lifecycle | golden vector + 6 lifecycle/transport tests | cross-platform socket/pipe and real model require target run |
| #192 | backend registry and release matrix | deterministic catalog, duplicate-ID and source-only tests | linked/fixture/real/benchmark levels are independent |
| #193 | GGUF identity and llama-server boundary | header/hash validation; missing executable is reported | real GGUF/Qwen run requires `llama-server` and checkpoint |
| #194 | MLX-LM/native promotion gate | host/import/parity/benchmark gate tests | Apple Silicon target and installed MLX are required |
| #195 | content-addressed offline Model Store | update, hash, tamper, rollback and traversal tests | network provisioning is intentionally outside the store |
| #196 | RAM/KV/recurrent/MTP/I/O estimator | formula and unknown/null provenance tests | backend collectors provide additional observed fields |
| #197 | orthogonal profiles and TurboQuant gate | profile conflict and quality-gate tests | TurboQuant is inactive without observed backend execution |
| #198 | separate Qwen weights/KV/recurrent/MTP state | explicit metadata and parity gate tests | model-name-only support is rejected |
| #199 | bounded Colibri expert streaming | real tiny shard reads, cache metrics and fault tests | deep target checkpoint and swap gate require hardware run |
| #200 | experimental dense layer streaming | tiny int8 parity, bounds and cancellation tests | no 27B/70B claim without target-host evidence |
| #201 | terminal physical receipts | redaction, identity, metrics and failure tests | missing collectors remain `unknown`, never zero |
| #202 | OpenAI HTTP/SSE adapter | same-daemon handle, auth, body and tool tests | embeddings stay disabled until separately proven |
| #203 | package install/update/rollback | clean temp install, protocol/checksum and model-preservation tests | published artifacts must be smoke-tested per target |

## Completion oracle

The minimum end-to-end path is now:

```text
binary handshake
  -> capabilities/evidence catalog
  -> content-addressed model identity
  -> estimate with provenance
  -> load/warm/generate stream
  -> terminal redacted receipt
  -> cancel/drain/unload/shutdown
```

The Python implementation is intentionally portable and fixture-backed on this
host. The registry remains honest about unavailable `llama-server`, MLX on a
non-Apple host, and unexecuted real checkpoints. Those gates are release
promotion requirements, not reasons to fabricate support.

## Validation command

```bash
python3 -m unittest discover -s tests/local_data_plane -v
```

The release helper used during this delivery was `simplicio v3.8.13`; its
Linux-x64 asset was verified against the published SHA-256 before use.
