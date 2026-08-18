# llama.cpp provider

The Local `LlamaCppProvider` is a process boundary around a pinned
`llama-server` executable. It validates a GGUF asset by extension, magic header
and SHA-256 before a load is attempted. The filename is never used as proof of
architecture or Qwen support.

`probe()` runs `llama-server --version` and reports `linked=true` only when the
executable responds successfully. `start_server()` binds loopback only and
keeps stdout/stderr behind the provider boundary. Stop is bounded and escalates
to kill after the grace period.

The optional Atomic-compatible path is selected with `backend=turboquant`,
`backend=llama-cpp-turboquant`, or `turboquant=true`. Before starting, Local
also runs `llama-server --help` and requires `--cache-type-k`,
`--cache-type-v`, and `turbo3` to be advertised. Only then does it pass
`--cache-type-k turbo3 --cache-type-v turbo3 --flash-attn auto -kvu` to the
server. An upstream server that lacks these options fails closed.

`TurboQuantBackendInstaller` follows the Atomic Agent managed-install pattern:
it selects an allow-listed platform asset from the Atomic fork's GitHub
releases, extracts it into a versioned directory under the Local home, and
writes `current.json` plus an install receipt containing the archive digest.
The installer is opt-in; Local never downloads a backend during a normal
inference request.

When the executable or model is unavailable, the provider returns an explicit
blocked state. It does not silently fall back to MLX, Ollama, a fixture, or a
different requested/effective backend. Recurrent state, tokenizer/chat
template, deterministic generation, cancellation and real-model promotion
require an observed backend run and are not inferred from a GGUF filename.
