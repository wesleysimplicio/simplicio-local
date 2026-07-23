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
