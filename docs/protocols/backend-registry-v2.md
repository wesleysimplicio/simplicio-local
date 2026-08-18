# Backend registry and evidence matrix

`local_data_plane.registry.BackendRegistry` is the single catalog used by the
v2 daemon's `capabilities` response. Entries are deterministic and sorted by
backend ID. Each entry contains platform, ISA, device, version/build identity,
formats, model families, methods, requested/effective identity, reason and
artifact references.

Evidence is monotonic but never inferred from a filename:

1. `source-present` — source marker exists;
2. `linked` — a compatible library or executable was discovered;
3. `fixture-executed` — a real bounded fixture ran and was checked;
4. `real-model-executed` — a published checkpoint ran;
5. `benchmarked-on-target` — a reproducible target-hardware benchmark exists.

The registry separates `available`, `supported`, `tested`, and `preferred`.
Proxy adapters (`ollama-proxy`, `custom-openai`) have `kind=proxy` and can
never be counted as native engines. A source-only entry remains unavailable
until an executable probe is observed. Requested and effective backend fields
are retained so a fallback cannot masquerade as the requested engine.
