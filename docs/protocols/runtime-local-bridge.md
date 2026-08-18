# Runtime → Local inference bridge

The architecture is intentionally split:

- `simplicio-runtime` owns route intent, admission, leases, fences, queue
  policy, deadlines, cancellation authority and final control-plane receipts;
- `simplicio-local` owns model handles, physical backends, prompt execution,
  device/storage work and observed measurements.

`local_data_plane.runtime_bridge.RuntimeInferenceBridge` ports the Runtime
`simplicio.inference-backend/v2` request/event boundary into the Local daemon.
It validates the Runtime envelope, requires a non-zero lease fence, rejects
expired deadlines, verifies the resolved prompt against its SHA-256/byte
reference, and maps the physical Local receipt into a hash-safe Runtime event
and `simplicio.inference-receipt/v2` receipt.

The bridge does not allocate leases, choose a backend, or silently fallback.
Those decisions remain Runtime-owned. A repeated `idempotency_key` is replayed
from the bridge cache without a second physical generation.

The low-level Local methods remain available for standalone operation. Runtime
clients should call `runtime_generate` with the v2 envelope and a
Runtime-resolved `prompt_text` whose hash matches `prompt.sha256`.

## Physical guarantees

- `capabilities` also returns `runtime_discovery`, one v2 discovery record per
  registered backend. Source presence is reported as advertised/degraded; it
  is never promoted to execution evidence.
- `load` accepts the Runtime `simplicio.inference-artifact-pin/v1` object. The
  pin is validated before a provider starts, and model/weights pins are
  compared with the bytes on disk. Local does not download mutable artifacts.
- `turboquant_compress` and `turboquant_decompress` expose a real CPU
  reference executor (`turboquant-kv-numpy`) for KV blocks. It performs the
  rotation, fixed Lloyd-Max codebook, bit-packing and per-vector norm
  correction, and reports measured bytes/error in its response.
- `turboquant_profile` on `runtime_generate` remains model-backend gated.
  Standard upstream `llama-cpp` does not expose its internal KV blocks. The
  Atomic-compatible `llama-cpp-turboquant` path is separate: it is admitted
  only after the executable advertises `turbo3` and is launched with the
  native KV-cache flags. On hosts without that binary, `allow_fallback=true`
  records compatibility explicitly.
- Physical failures return an error frame together with a terminal Runtime
  event, a `simplicio.local.physical-receipt/v1` receipt, and the Runtime
  receipt hash. The outer response is not marked `ok`.

Minimal request shape:

```json
{
  "method": "runtime_generate",
  "request": {
    "schema": "simplicio.inference-backend/v2",
    "request_id": "request-1",
    "correlation_id": "correlation-1",
    "idempotency_key": "idem-1",
    "owner": "simplicio-runtime",
    "lease_id": "lease-1",
    "fence": 1,
    "prompt": {"locator": "memory://prompt-1", "sha256": "<64 hex>", "byte_len": 5},
    "prompt_text": "hello",
    "limits": {"max_output_tokens": 8, "temperature": 0, "top_p": 1, "stop_sequences": []},
    "intents": {
      "weights_profile": "balanced",
      "cache_profile": "balanced",
      "storage_profile": "resident",
      "device_profile": "cpu",
      "workload_class": "interactive",
      "allow_fallback": false
    },
    "deadline_unix_ms": 4102444800000,
    "cancellation_token": "cancel-1"
  }
}
```

The CPU reference evidence for this checkout is stored in
`docs/benchmarks/turboquant-kv-cpu-2026-08-18.json`. It is useful for contract
and quality tests; it is not a claim of fused GPU attention performance.
