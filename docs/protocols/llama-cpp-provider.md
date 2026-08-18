# llama.cpp provider

The Local `LlamaCppProvider` is a process boundary around a pinned
`llama-server` executable. It validates a GGUF asset by extension, magic header
and SHA-256 before a load is attempted. The filename is never used as proof of
architecture or Qwen support.

`probe()` runs `llama-server --version` and reports `linked=true` only when the
executable responds successfully. `start_server()` binds loopback only and
keeps stdout/stderr behind the provider boundary. Stop is bounded and escalates
to kill after the grace period.

When the executable or model is unavailable, the provider returns an explicit
blocked state. It does not silently fall back to MLX, Ollama, a fixture, or a
different requested/effective backend. Recurrent state, tokenizer/chat
template, deterministic generation, cancellation and real-model promotion
require an observed backend run and are not inferred from a GGUF filename.
