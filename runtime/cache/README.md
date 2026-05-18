# Cache

Home for prefix cache, SSD cold cache, reusable session cache components, and
MoE sparsity-pattern reuse surfaces.

- `SparsityAwareCache` keys entries by `family + expert-pattern hash`.
- MoE adapters use it to surface hit/miss effectiveness without changing
  executable expert selection semantics.
