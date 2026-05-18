# US4 V6 - Apple Edition

> Universal State Runtime for local LLM inference on Apple Silicon.
> EN. Versao pt-BR: [README.pt-BR.md](README.pt-BR.md).

![us4-v6-simplicio-apple](us4-v6-simplicio-apple.PNG)

## What this repo is

This repository is the planning and bootstrap base for **US4 V6 Apple Edition**, the Apple Silicon branch of the Universal State Runtime.

Today the repo contains two things:

1. the **llm-project-mapper/bootstrap layer** used to scaffold disciplined AI-assisted work;
2. the **project plan** for the C++ runtime that will be built across 12 sprints.

The C++ runtime itself has **not** been scaffolded yet. That work starts in Sprint 01.

Reference source: [US4-V6-simplicio.md](US4-V6-simplicio.md).

## Product scope

US4 V6 Apple Edition targets local inference for:

- dense adapters: Qwen, Llama, Gemma;
- MoE adapters: DeepSeek, Kimi, MiniMax, GLM;
- low-memory adapters: BitNet and PT-BitNet ternary;
- Apple backends: MLX, Metal, NEON/Accelerate, and optional ANE on M5+.

The product is explicitly:

- single-machine first;
- correctness-gated before performance claims;
- CLI + library, not a GUI app;
- Apple-specific in this edition.

## Current repo status

**Planning is now filled in at the project level.**

- Product docs define vision, domain, personas, runtime modes, and compatibility targets.
- Architecture docs define the runtime boundaries, contracts, and coding patterns for C++/Metal/MLX work.
- Workflow docs define how implementation begins from the current starter/bootstrap phase and transitions into the real runtime repo layout.
- Sprint 01 is decomposed into executable tasks.

What still does not exist yet:

- `runtime/`
- `CMakeLists.txt`
- `build/`
- production `us4-cli`
- release automation for the Apple runtime

Those artifacts are planned, not present.

## Planned stack

- C++20 + CMake + Ninja
- MLX as primary tensor/runtime path on Apple Silicon
- Metal for measured hot kernels not well covered by MLX
- NEON / Accelerate as CPU fallback
- ANE as opt-in offload path on M5+
- GoogleTest + CTest for unit and regression
- Playwright for CLI E2E evidence

## Working model

The repo follows the `AGENTS.md` ecosystem. Core instructions live in:

- [AGENTS.md](AGENTS.md)
- [CLAUDE.md](CLAUDE.md)
- [.github/copilot-instructions.md](.github/copilot-instructions.md)

All technical work is expected to follow the loop:

`read task -> plan -> edit -> format/lint -> unit -> e2e -> regression -> fix -> commit -> PR`

## Roadmap

| Sprint | Theme |
|---|---|
| 01 | Foundations and Skeleton |
| 02 | CPU Scalar Baseline |
| 03 | MLX and Metal Skeleton |
| 04 | NEON Hot Paths |
| 05 | BitNet and Ternary |
| 06 | KV Memory Architecture |
| 07 | Llama Adapter |
| 08 | MoE Foundation |
| 09 | MoE Advanced |
| 10 | Continuous Batching and Speculative Decoding |
| 11 | ANE M5+ Offload |
| 12 | Auto-Tune and v1.0 Release |

Details:

- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\BACKLOG.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/BACKLOG.md)
- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\TIMELINE.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/TIMELINE.md)

## Repo layout today

```text
.specs/        planning source of truth
.agents/       custom agents
.skills/       reusable skills
.claude/       Claude hooks/settings
.codex/        Codex hooks/settings
.github/       starter CI/DoD and templates
bin/           llm-project-mapper CLI
test/          starter self-tests
tests/e2e/     starter Playwright placeholder
```

## Future runtime layout

```text
runtime/
  core/
  adapters/
  memory/
  kv/
  cache/
  moe/
  metal/
  mlx/
  neon/
  ane/
  speculative/
  tuning/
  telemetry/
  benchmarks/
```

## Out of scope

- cloud or distributed inference;
- training or fine-tuning;
- non-Apple hardware in this edition;
- GUI desktop shell before CLI and library are stable.
