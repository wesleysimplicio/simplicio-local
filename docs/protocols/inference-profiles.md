# Orthogonal inference profiles

The Local profile separates storage (`resident`, `mmap`, `expert-stream`,
`layer-stream`), weight quantization, KV quantization, device offload,
speculation and workload class. This prevents a single "low memory" switch from
silently changing multiple physical behaviors.

Expert/layer streaming is rejected for interactive workloads and must be marked
background or deep-offline. Experimental lanes must opt in explicitly.

TurboQuant is not a capability flag. When requested, it remains inactive until
the selected backend has observed fixture or stronger execution evidence and a
reference-versus-candidate quality vector passes the configured relative-error
gate. Weights and KV promotion are evaluated independently.
