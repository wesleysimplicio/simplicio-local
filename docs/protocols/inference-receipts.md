# Physical inference receipts

Every Local `generate` ends with a terminal success, cancellation or failure
receipt. The receipt separates requested and effective backend/model/profile,
records the daemon/platform identity, and labels each metric as observed,
estimated or unknown with units, source and reason.

The default telemetry path never stores raw prompts or generated text. It keeps
SHA-256 hashes only when a caller explicitly records them. Process CPU and
latency are observed at the receipt boundary; backend-specific I/O, memory,
thermal and swap values remain unknown unless a collector supplies them.

Receipts use a versioned schema and are published atomically. A failure before
terminal completion is still a failure receipt when the process boundary can
produce one; no zero-filled success is synthesized after a crash.
