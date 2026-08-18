# Qwen hybrid state

The Local keeps four independently identified components for a hybrid Qwen
run: content-addressed weights, attention KV, recurrent state and MTP state.
They cannot share an identity accidentally, and each can carry a separate
budget, placement and lifecycle.

`probe_metadata` requires explicit architecture, recurrent-layer and MTP-depth
metadata. A model name such as `Qwen3.6-27B` is not evidence of support.
Promotion additionally requires fixture-or-stronger execution evidence and
reference-versus-candidate output parity. Missing metadata, aliasing, or parity
failure leaves the requested model blocked rather than silently selecting a
different effective model.
