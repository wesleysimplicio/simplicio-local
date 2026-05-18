# US4 V6 - Apple Edition

> Universal State Runtime para inferencia LLM local em Apple Silicon.
> pt-BR. EN version: [README.md](README.md).

![us4-v6-simplicio-apple](us4-v6-simplicio-apple.PNG)

## O que este repo eh

Este repositorio e a base de planejamento e bootstrap do **US4 V6 Apple Edition**, a edicao Apple Silicon do Universal State Runtime.

Hoje ele contem duas camadas:

1. a **camada llm-project-mapper/bootstrap**, usada para estruturar trabalho com agentes;
2. o **planejamento do projeto** do runtime C++ que sera construido ao longo de 12 sprints.

O runtime C++ em si **ainda nao foi scaffoldado**. Esse trabalho comeca no Sprint 01.

Fonte de referencia: [US4-V6-simplicio.md](US4-V6-simplicio.md).

## Escopo do produto

O US4 V6 Apple Edition mira inferencia local para:

- adapters dense: Qwen, Llama, Gemma;
- adapters MoE: DeepSeek, Kimi, MiniMax, GLM;
- adapters low-memory: BitNet e PT-BitNet ternary;
- backends Apple: MLX, Metal, NEON/Accelerate e ANE opcional em M5+.

O produto eh explicitamente:

- single-machine first;
- correctness-first antes de qualquer claim de performance;
- CLI + biblioteca, nao app GUI;
- especifico para Apple nesta edicao.

## Estado atual do repo

**O planejamento agora esta preenchido no nivel de projeto.**

- Os docs de produto definem visao, dominio, personas, modos de runtime e alvos de compatibilidade.
- Os docs de arquitetura definem boundaries do runtime, contratos centrais e padroes de codigo para C++/Metal/MLX.
- Os docs de workflow explicam como a implementacao sai do estado atual de starter/bootstrap e entra no layout real do runtime.
- O Sprint 01 foi decomposto em tasks executaveis.

O que ainda nao existe:

- `runtime/`
- `CMakeLists.txt`
- `build/`
- `us4-cli` de producao
- automacao de release do runtime Apple

Esses artefatos estao planejados, nao presentes.

## Stack planejada

- C++20 + CMake + Ninja
- MLX como caminho primario de tensor/runtime no Apple Silicon
- Metal para kernels quentes medidos que o MLX nao cobre bem
- NEON / Accelerate como fallback de CPU
- ANE como caminho opt-in em M5+
- GoogleTest + CTest para unit e regression
- Playwright para evidencia E2E da CLI

## Modelo de trabalho

O repo segue o ecossistema `AGENTS.md`. As instrucoes centrais vivem em:

- [AGENTS.md](AGENTS.md)
- [CLAUDE.md](CLAUDE.md)
- [.github/copilot-instructions.md](.github/copilot-instructions.md)

Todo trabalho tecnico deve seguir o loop:

`ler task -> planejar -> editar -> format/lint -> unit -> e2e -> regression -> corrigir -> commit -> PR`

## Roadmap

| Sprint | Tema |
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

Detalhes:

- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\BACKLOG.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/BACKLOG.md)
- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\TIMELINE.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/TIMELINE.md)

## Layout do repo hoje

```text
.specs/        fonte de verdade do planejamento
.agents/       agentes customizados
.skills/       skills reutilizaveis
.claude/       hooks/settings do Claude
.codex/        hooks/settings do Codex
.github/       CI/DoD do starter e templates
bin/           CLI do llm-project-mapper
test/          self-tests do starter
tests/e2e/     placeholder Playwright do starter
```

## Layout futuro do runtime

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

## Fora de escopo

- inferencia em nuvem ou distribuida;
- treino ou fine-tuning;
- hardware nao-Apple nesta edicao;
- shell GUI antes de CLI e biblioteca estarem estaveis.
