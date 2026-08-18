# Physical resource estimator

The estimator reports weights, KV cache, recurrent state, MTP state, working
buffers, disk footprint, read bytes and total resident memory. Every value has
`observed`, `estimated`, `derived` or `unknown` semantics, a unit, source and a
reason when absent. Unknown values are `null`; zero is never used as a synonym
for unavailable.

The KV formula is explicit:

```text
2 * context_tokens * layers * kv_heads * head_dim * dtype_bytes * batch
```

The factor two accounts for K and V. It is only emitted when all dimensions are
declared. Asset size and process I/O counters are observed from the filesystem
or process boundary; resident totals remain unknown until every component is
known. Estimate-versus-observed deltas are derived only after both sides exist.
