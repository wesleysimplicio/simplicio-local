# US4 V6 — Apple Edition

> Universal State Runtime for local LLM inference on Apple Silicon (M1 → M5+).
> EN. Versão pt-BR: [README.pt-BR.md](README.pt-BR.md).

![us4-v6-simplicio-apple](us4-v6-simplicio-apple.PNG)

## What

US4 V6 is a C++ runtime that runs modern LLM families (DeepSeek MoE, Kimi MoE, MiniMax, GLM, Qwen, Llama, Gemma, BitNet, PT-BitNet Ternary) **locally** on Apple Silicon, with adaptive backend dispatch across **CPU scalar / NEON / Metal / MLX / ANE (M5+)**, hot-cold KV paging, MoE expert paging, speculative decoding, continuous batching, and hardware-aware auto-tuning across 7 RAM tiers (8 GB → 192 GB+).

Runtime modes: `FULL`, `BALANCED`, `DEGRADED`, `ULTRA_LOW`, `MICRO`, `MICRO_PLUS` — auto-selected by hardware probe at boot, manually overridable via CLI flag.

Reference master spec: [`US4-V6-simplicio.md`](../US4-V6-simplicio.md).

## Stack

- C++17/20 + CMake
- MLX (Apple ML eXecution framework)
- Metal (compute kernels, command queues, unified-memory KV)
- NEON SIMD (ARMv8.4-A+)
- ANE (Apple Neural Engine, dense layer offload on M5+)
- GoogleTest (unit), Playwright (CLI/UX E2E), Ralph Loop (autonomous fix/verify)
- GitHub Actions (CI + DoD gates)

## Status

**Planning complete.** All 12 sprints scaffolded in [`.specs/sprints/`](.specs/sprints/). Implementation hasn't started yet — architecture `DESIGN.md`/`PATTERNS.md`/ADRs are filled in **during** each sprint's first task, not upfront.

| Sprint | Theme |
|---|---|
| 01 | Foundations & Skeleton |
| 02 | CPU Scalar Baseline |
| 03 | MLX + Metal Skeleton |
| 04 | NEON Hot Paths |
| 05 | BitNet + Ternary |
| 06 | KV Memory Architecture |
| 07 | Llama Adapter |
| 08 | MoE Foundation (DeepSeek + Kimi) |
| 09 | MoE Advanced (MiniMax + GLM + SP-MoE) |
| 10 | Batching + Speculative Decoding |
| 11 | ANE M5+ Offload |
| 12 | Auto-Tune + Release v1.0 |

Full matrix: [`.specs/sprints/BACKLOG.md`](.specs/sprints/BACKLOG.md).

## How the agent works here

This repo follows the **Agentic Starter** convention. Master instruction file: [`AGENTS.md`](AGENTS.md) (mirrored at [`CLAUDE.md`](CLAUDE.md) and [`.github/copilot-instructions.md`](.github/copilot-instructions.md)).

Every technical task goes through the mandatory loop: read task → plan → load context → edit → lint → unit → Playwright E2E (trace+screenshot+video) → fix → conventional commit (English) → PR with DoD checklist.

DoD gate (enforced by [`.github/workflows/dod.yml`](.github/workflows/dod.yml)): lint green, unit green with ≥80% coverage on touched files, Playwright E2E green with evidence, all AC checked, ADR added if architectural decision, changelog updated if release-relevant.

## Repo layout

```
.specs/
  product/       VISION.md, DOMAIN.md, PERSONAS.md
  architecture/  DESIGN.md, PATTERNS.md, ADR-*.md (filled during sprints)
  workflow/      WORKFLOW.md, CONTRIBUTING.md, RELEASE.md
  sprints/       BACKLOG.md, sprint-01..12/SPRINT.md
.skills/         reusable agent capabilities
.agents/         custom sub-agents (ralph-loop, tdd, reviewer, architect)
.claude/         settings + hooks (post-edit lint, pre-commit gate)
.github/         workflows (ci.yml, dod.yml), PR/Issue templates
runtime/         C++ source (created in sprint-01: core, adapters, memory, kv, cache, moe, metal, mlx, neon, ane, speculative, tuning, telemetry, benchmarks)
```

## Out of scope

- Cloud/distributed inference (single-machine focus).
- Training/fine-tuning (inference only).
- Non-Apple hardware → see [US4 V6 Windows Edition](https://github.com/wesleysimplicio/us4-v6-simplicio-windows).
- GUI desktop app (CLI + library only).

## License

TBD (will be declared before v1.0 release in Sprint 12).
