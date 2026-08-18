# Colibri expert streaming

`ColibriBackend` accepts content-addressed shard descriptors instead of
hardcoded paths. It reads only routed experts, maintains a bounded LRU cache,
validates optional SHA-256 digests, and returns no partial output on missing,
short or corrupt reads.

The terminal metrics include bytes read, routed token count, cache
hit/miss/eviction counts and observed bytes per token. Swap is `unknown` unless
an OS collector supplies a measurement; zero is not fabricated. Cancellation is
checked before each routed read and returns a cancelled status without treating
partial output as success.

This lane is specialized for background/deep-offline MoE workloads. It does not
replace the dense llama.cpp baseline or authorize global workload policy.
