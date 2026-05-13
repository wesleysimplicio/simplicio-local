# US4 V6 — Apple Edition

> Universal State Runtime pra inferência LLM local em Apple Silicon (M1 → M5+).
> pt-BR. EN version: [README.md](README.md).

![us4-v6-simplicio-apple](us4-v6-simplicio-apple.PNG)

## O que é

US4 V6 é um runtime C++ que roda famílias modernas de LLM (DeepSeek MoE, Kimi MoE, MiniMax, GLM, Qwen, Llama, Gemma, BitNet, PT-BitNet Ternary) **localmente** em Apple Silicon, com dispatch adaptativo de backend entre **CPU scalar / NEON / Metal / MLX / ANE (M5+)**, paginação hot-cold de KV, paginação de experts MoE, decodificação especulativa, batching contínuo e auto-tuning ciente de hardware em 7 tiers de RAM (8 GB → 192 GB+).

Modos de runtime: `FULL`, `BALANCED`, `DEGRADED`, `ULTRA_LOW`, `MICRO`, `MICRO_PLUS` — auto-selecionados pelo probe de hardware no boot, sobrescrevíveis via flag de CLI.

Spec master de referência: [`US4-V6-simplicio.md`](../US4-V6-simplicio.md).

## Stack

- C++17/20 + CMake
- MLX (Apple ML eXecution framework)
- Metal (kernels de compute, command queues, KV em unified memory)
- NEON SIMD (ARMv8.4-A+)
- ANE (Apple Neural Engine, offload de camada densa em M5+)
- GoogleTest (unit), Playwright (CLI/UX E2E), Ralph Loop (fix/verify autônomo)
- GitHub Actions (CI + gates de DoD)

## Status

**Planejamento completo.** Os 12 sprints estão scaffolded em [`.specs/sprints/`](.specs/sprints/). A implementação ainda não começou — `DESIGN.md`/`PATTERNS.md`/ADRs de arquitetura são preenchidos **durante** a primeira task de cada sprint, não antes.

| Sprint | Tema |
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

Matriz completa: [`.specs/sprints/BACKLOG.md`](.specs/sprints/BACKLOG.md).

## Como o agente trabalha aqui

Este repo segue a convenção **Agentic Starter**. Arquivo master de instruções: [`AGENTS.md`](AGENTS.md) (espelhado em [`CLAUDE.md`](CLAUDE.md) e [`.github/copilot-instructions.md`](.github/copilot-instructions.md)).

Toda task técnica passa pelo loop obrigatório: ler task → planejar → carregar contexto → editar → lint → unit → Playwright E2E (trace+screenshot+video) → corrigir → commit convencional (em inglês) → PR com checklist DoD.

Gate de DoD (forçado por [`.github/workflows/dod.yml`](.github/workflows/dod.yml)): lint verde, unit verde com ≥80% de cobertura nos arquivos tocados, Playwright E2E verde com evidência, todos os AC marcados, ADR adicionado se decisão arquitetural, changelog atualizado se release-relevant.

## Layout do repo

```
.specs/
  product/       VISION.md, DOMAIN.md, PERSONAS.md
  architecture/  DESIGN.md, PATTERNS.md, ADR-*.md (preenchidos durante os sprints)
  workflow/      WORKFLOW.md, CONTRIBUTING.md, RELEASE.md
  sprints/       BACKLOG.md, sprint-01..12/SPRINT.md
.skills/         capacidades reutilizáveis dos agentes
.agents/         sub-agentes customizados (ralph-loop, tdd, reviewer, architect)
.claude/         settings + hooks (post-edit lint, pre-commit gate)
.github/         workflows (ci.yml, dod.yml), templates de PR/Issue
runtime/         código C++ (criado no sprint-01: core, adapters, memory, kv, cache, moe, metal, mlx, neon, ane, speculative, tuning, telemetry, benchmarks)
```

## Fora de escopo

- Inferência em nuvem/distribuída (foco em máquina única).
- Treino/fine-tuning (somente inferência).
- Hardware não-Apple → ver [US4 V6 Windows Edition](https://github.com/wesleysimplicio/us4-v6-simplicio-windows).
- App desktop GUI (somente CLI + biblioteca).

## Licença

TBD (declarada antes do release v1.0 no Sprint 12).
