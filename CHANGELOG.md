# Changelog

All notable changes to **US4 V6 Apple Edition** are recorded here. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adopts [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-05-27

### Changed

- `README.md` section 6.1 now documents the `US4_SERVE_CHAT_BACKEND=ollama`
  mode end-to-end. New content: the `US4_SERVE_CHAT_BACKEND` and
  `US4_SERVE_CHAT_UPSTREAM` env vars added to the configuration table; a
  worked example wiring us4-v6 as a front for an already-running Ollama
  daemon (`ollama serve` + `ollama pull qwen2.5-coder:7b` + us4-v6 with
  `CHAT_BACKEND=ollama`); an ASCII wire diagram showing chat going to
  Ollama on `11434` and embeddings staying in-process via mlx-embeddings;
  a list of the three situations where this mode beats the MLX path
  (Ollama-based model management, single OpenAI-shape facade in front of
  Ollama shared with other tools, machine that cannot host both an MLX
  child and Ollama). Section 6.6 troubleshooting matrix grew two rows
  covering the most likely failures in Ollama mode (`chat upstream
  unreachable: Connection refused`, `model "<id>" not found`). Validated
  with `qwen2.5-coder:7b` on an M1 8 GB box: chat round-trip through
  us4-v6 -> Ollama returned a 78-token FizzBuzz response in ~22 s wall
  (~3.5 tok/s), confirming the proxy path works under tight RAM.

## [0.2.2] - 2026-05-27

### Changed

- Expanded `README.md` section 6 ("Serve OpenAI-Compatible Endpoint") into a
  full local-LLM guide framed as an Ollama-compatible drop-in. New
  subsections cover: Python sidecar path (no C++ build required, with venv
  setup avoiding `externally-managed-environment`), C++ CLI wrapper path,
  smoke-test curl recipes for `/v1/chat/completions` and `/v1/embeddings`,
  pointing arbitrary OpenAI-shape clients at the local endpoint, an Apple
  Silicon hardware sizing table (M1 8 GB to M4 Max 64 GB+), and a
  troubleshooting matrix for the most common first-run failures
  (`mlx-embeddings is not installed`, `externally-managed-environment`,
  `Address already in use`, missing native binary, ignored `--model` flag,
  swap thrashing on undersized RAM). Documents that the sidecar is
  configured via environment variables (`US4_SERVE_*`) and not CLI flags.

## [0.2.1] - 2026-05-27

### Fixed

- `POST /v1/embeddings` returned 500 `embedding failed` with the default
  `embeddinggemma-300m-bf16` model. Root cause: `mlx-embeddings 0.1.0` ships a
  `generate()` helper that calls `model(**inputs)` with key `input_ids`, but
  the `gemma3_text` model class expects `inputs=`. Replaced the helper call in
  `EmbeddingsBackend.embed` with explicit tokenization and a signature-aware
  dispatch (`inputs=` first, fall back to `input_ids=` on `TypeError`) so the
  backend stays model-agnostic across BERT-, Gemma3-, Qwen3-, and ModernBERT-
  style embedders. Smoke: `/v1/embeddings` returns 768-dim vectors for the
  default model; serve E2E suite still 5/5.

## [0.2.0] - 2026-05-27

### Added

- `us4-cli serve` subcommand exposing a local OpenAI-compatible HTTP endpoint
  on Apple Silicon. Routes:
  - `POST /v1/chat/completions` and `POST /v1/completions` proxied to
    `mlx_lm.server` running as a managed child process on `PORT + 1`.
  - `POST /v1/embeddings` served in-process by an MLX embeddings backend.
  - `GET /v1/models` aggregating the active chat and embedding model ids.
  - `GET /health` (alias `/v1/health`) returning liveness and per-backend
    enablement flags.
- Python sidecar `scripts/openai_serve.py` (stdlib `http.server` only, no
  FastAPI/uvicorn) wired by the CLI via `execvp(python3, script)`.
- Dependency manifest `scripts/requirements-serve.txt` pinning `mlx`,
  `mlx-lm`, and `mlx-embeddings` ranges used by the serve sidecar.
- Contract document `.specs/runtime/SERVE-OPENAI.md` covering endpoints,
  request/response shapes, environment knobs, exit codes, and security posture.
- Defaults: chat model `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`,
  embedding model `mlx-community/embeddinggemma-300m-bf16` (overridable via
  `--chat-model` / `--embed-model` or `US4_SERVE_CHAT_MODEL` /
  `US4_SERVE_EMBED_MODEL`).
- Backend opt-out flags `--no-chat` / `--no-embed` (env:
  `US4_SERVE_DISABLE_CHAT` / `US4_SERVE_DISABLE_EMBED`) so CI smoke and partial
  installs do not require downloading both models.
- CLI script-path overrides `US4_SERVE_SCRIPT` and `US4_SERVE_PYTHON` for
  packaged installs and custom interpreter layouts.
- Playwright E2E spec `tests/e2e/us4-cli-serve.spec.ts` covering health,
  models, disabled-backend, and 404 paths with both backends disabled.

### Changed

- Bumped project version `0.1.49` -> `0.2.0` (CMakeLists.txt, propagates to
  `us4::kUs4Version` via `runtime/core/version.h.in`).
- `us4-cli --help` usage block now documents the `serve` subcommand.

### Integration

- `simplicio-cli` (and any OpenAI-compatible client) can target the local
  endpoint with a single env var, e.g.
  `SIMPLICIO_BASE_URL=http://127.0.0.1:8080/v1` plus `OPENAI_API_KEY=anything`.

### Notes

- The serve path is opt-in. The native runtime, fixtures, probe, and existing
  CLI subcommands are unchanged.
- Real chat completions require `pip install -r scripts/requirements-serve.txt`
  and a working MLX install on Apple Silicon.

## [0.1.x] - prior releases

See git history (`git log --oneline`) for pre-0.2.0 increments.

[0.2.0]: https://github.com/wesleysimplicio/us4-v6-simplicio-apple/releases/tag/v0.2.0
