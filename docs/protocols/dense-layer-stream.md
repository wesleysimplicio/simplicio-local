# Experimental dense layer streaming

The dense stream lane consumes versioned layer descriptors with explicit
offsets, dimensions, dtype, scale and optional checksum. It supports bounded
float32 and int8 slabs, validates ranges before reading, and keeps at most two
slab-sized weight buffers in its accounting.

The executor is opt-in for `background`/`deep-offline` workloads. Interactive
profiles are rejected. Cancellation, short reads, checksum failures and
dimension mismatches return a failed/cancelled result with an empty output;
partial activations are never reported as a successful generation.

Metrics are observed from the executor: bytes read, bytes per token, peak slab
bytes, slot bound and elapsed time. This implementation proves the tiny
mechanism only; it makes no 27B/70B-in-16GB claim without a target-host run.
