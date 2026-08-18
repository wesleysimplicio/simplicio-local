# Simplicio inference-backend/v2

The Local process owns the physical inference data plane: model handles,
weights, caches, devices, loading, generation, cancellation, draining and
unloading. It does not own workspace effects, tool execution, Git, global
selection policy or completion receipts.

## Private transport

The canonical transport is a framed binary stream over stdio. The first
implementation also provides the same frame contract to a Unix socket or
Windows named-pipe adapter. JSON is not the internal source of truth; the
payload uses a tagged value codec with deterministic map ordering.

Each frame contains:

`magic (SLV2) | version | kind | flags | request-id | payload length | CRC32`

Frames are bounded to 8 MiB, nesting to 32 levels, and collections to 100,000
items. Unknown headers, invalid lengths, bad UTF-8, duplicate map keys,
truncation and checksum failures are rejected before dispatch.

## Methods

`handshake`, `capabilities`, `estimate`, `load`, `warm`, `generate`, `cancel`,
`status`, `drain`, `unload`, and `shutdown` are the version-2 lifecycle surface.
Every response includes an explicit success/error result. Streaming generation
emits token event frames followed by one terminal response or a cancellation
error.

The daemon always advertises `effect_authority=none`. Status intentionally
contains lifecycle and handle identity only; prompts and generated text are not
persisted or emitted by status.

## Running the fixture daemon

```bash
python3 bin/local-daemon.py --standalone
```

The fixture provider exists to prove framing and lifecycle. It must not be
reported as a real-model or target-hardware execution. Backend promotion and
physical evidence are implemented by the registry and telemetry lanes.
