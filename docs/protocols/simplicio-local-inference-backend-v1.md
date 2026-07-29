# `simplicio.local-inference-backend/v1`

This is the external contract between the local inference engine and the
Simplicio Runtime/Inference Steward. Runtime owns admission, leases, queues,
budgets and effect authority. This repository only reports capabilities,
estimates resources and executes inference after a valid Runtime lease.

`us4-cli backend probe --json` is read-only: it does not load weights, spawn an
engine or claim an effective model. Capability states distinguish
`implemented`, `implemented-unverified-on-host`, `experimental` and `planned`.

`us4-cli backend estimate` fails closed when projected RSS exceeds either
available memory or the hard limit, when model storage is insufficient, or
when an interactive workload lacks an explicit Runtime policy. Unknown
latency and throughput are emitted as `null` with a reason.

The reference `LeaseRegistry` defines single-flight `(model, profile)` leases,
monotonic fencing and validated lifecycle transitions. Runtime remains the
durable authority; the registry is an adapter contract, not a second
coordinator. Receipts identify requested/effective models, hash output, expose
only an allowlisted metrics set and always declare `effect_authority: none`.


## Opt-in LiteRT-LM package provisioning

us4-cli backend install litert --dry-run --json resolves the pinned simplicio.local-litert-package/v1 manifest without network or filesystem effects. The plan exposes the component versions, Apache-2.0 license, selected platform artifact, byte size, SHA-256, cache destination, and runtime_effect: package-cache-only.

An actual install requires the explicit --yes flag. It streams either the pinned HTTPS artifact or a caller-supplied local fixture into an external managed cache, verifies size and SHA-256, rejects unsafe archive members and symlinks, then publishes the artifact and install-receipt.json atomically. The checkout is rejected as a cache destination. This operation does not start inference, acquire a lease, or replace an external server; Runtime remains the authority for those effects.

The LiteRT-LM package manifest is pinned to LiteRT-LM 0.11.0 and LiteRT 2.0.2 in this slice. A successful package receipt is not evidence of a real model completion, stream/cancel behavior, throughput, NPU readiness, or the full platform matrix; those #177 DoD items require separate measured evidence.

us4-cli doctor --json reports accelerator configuration separately from observed host capability. Configuration alone is never promoted to observed hardware readiness; absent GPU/NPU evidence remains not-observed.


Offline verification and rollback are explicit package-cache operations. us4-cli backend install litert --verify --json reads only the managed install-receipt.json and artifact, checks the pinned manifest, size and SHA-256, and returns verified, offline: true, or a typed cache miss/integrity failure without network access or writes. us4-cli backend install litert --rollback --yes --json (with --uninstall as an alias) removes only the artifact and receipt named by that managed receipt; it refuses missing confirmation and preserves unmanaged files, models, and configuration. This is not yet proof of a real LiteRT-LM model completion or execution receipt for the full #177 DoD.
