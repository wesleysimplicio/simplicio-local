# Hardware Probe and Runtime Mode

> Origem: Sprint 01 / T01.4. Define o que o `HardwareProbe` mede, quais sao as
> responsabilidades do probe vs do `RuntimeModeSelector`, e como o probe mapeia
> hardware Apple Silicon para um modo de runtime canonico.

## 1. Modos canonicos

Sete modos. Ordem fixa. Nenhum outro nome eh aceito como modo.

```text
FULL
BALANCED_PLUS
DEGRADED
ULTRA_LOW
MICRO
MICRO_PLUS
NANO
```

Restricoes:

- a taxonomia eh imutavel sem ADR.
- transicoes dentro de uma sessao **so podem degradar** (FULL -> ... -> NANO).
- nenhuma area do codigo deve introduzir aliases como "low", "tiny", "auto1".

## 2. Mapeamento memoria -> modo default

| Unified memory | Modo default |
|---|---|
| 128 GB | `FULL` |
| 96 GB | `BALANCED_PLUS` |
| 64 GB | `DEGRADED` |
| 48 GB | `ULTRA_LOW` |
| 32 GB | `MICRO` |
| 24 GB | `MICRO_PLUS` |
| 16 GB | `NANO` |

Regras:

- O probe escolhe pelo tier mais proximo abaixo (16 GB -> NANO, 20 GB -> NANO,
  24 GB -> MICRO_PLUS, etc.).
- Hardware nao-Apple-Silicon (ex.: x86, runner Linux) cai em `NANO` por
  contrato; nao implica que execucao funcione, so reporta tier seguro.
- Apple Silicon abaixo de 16 GB nao eh suportado: probe retorna `NANO` mas
  marca `aneEligible=false` e emite warning.

## 3. Responsabilidades do `HardwareProbe`

O probe **observa**, nao decide policy.

Deve coletar:

- `platform`: SO host (`darwin`, `linux`, `win32`, ...).
- `arch`: arquitetura host (`arm64`, `x86_64`, ...).
- `cpuModel`: string do modelo de CPU vinda do SO.
- `logicalCores`: numero de cores logicos.
- `totalMemoryBytes` / `totalMemoryGiB`: memoria total fisica.
- `appleSilicon`: boolean (true se Apple M1+).
- `aneEligible`: boolean (true so em M5+ com SO compativel).
- `chip`: identificacao curta (ex.: `M1`, `M2 Pro`, `M3 Max`, `M5`), best-effort.
- `has_mlx`, `has_metal`, `has_neon`: capability flags binarias.
- `neon_vector_bits`: 128 em ARMv8.0+, 0 fora de ARM.
- `has_performance_cores`, `has_efficiency_cores`: presenca de clusters P/E.
- Diagnostico Metal opt-in: `metal_device`, `metal_queue_label`,
  `metal_threads_per_group`, `metal_init_stage`, `metal_queue_created`,
  `metal_autorelease_boundary_requested`, `metal_objc_boundary_supported`,
  `metal_reason`.
- `supports_unified_memory`: derivado de `appleSilicon` + capability MLX.

O probe **nao**:

- escolhe modo final;
- decide backend a ser executado;
- carrega modelo ou pesos;
- inicializa subsistemas pesados (KV, MoE, scheduler).

## 4. Responsabilidades do `RuntimeModeSelector`

O selector recebe um snapshot do probe e devolve um `RuntimeMode`.

Regras:

- input: snapshot read-only do probe + flag opcional `--mode <value>`.
- output: `{ requested, selected, taxonomy, source }`.
- `source` enumera de onde veio a decisao:
  - `memory-tier` (default automatico),
  - `explicit-flag` (usuario passou `--mode`),
  - `host-fallback` (host nao-Apple-Silicon),
  - `degraded-by-pressure` (futuro, transicao em sessao).
- nao escolhe modo fora da taxonomia.
- nao pode subir modo dentro de uma sessao (so igualar ou degradar).

## 5. Backend hint vs runtime mode

Mode controla **policy de memoria/desempenho**, nao backend.

Sugestoes default por modo (ainda assim verificadas pelo `BackendSelector`):

| Mode | Backend default sugerido |
|---|---|
| FULL | `metal` |
| BALANCED_PLUS | `metal` ou `mlx` |
| DEGRADED | `mlx` |
| ULTRA_LOW | `mlx` ou `neon` |
| MICRO | `neon` |
| MICRO_PLUS | `neon` |
| NANO | `scalar` |

Se o backend pedido nao tiver capability, o `BackendSelector` aplica o
fallback documentado em `ADR-003`.

## 6. Saida observavel

A saida do probe sempre flui pelos contratos JSON em `.specs/runtime/CLI-CONTRACT.md`.

- Texto: resumo `mode: <selected>`, `platform: <platform>`, `memory: <gib>`.
- JSON: bloco `probe` (capability hardware) + bloco `mode` (taxonomia + escolha).

## 7. Testes

- Smoke JS: `test/probe-mode.smoke.test.js`.
- Playwright: `tests/e2e/us4-cli.spec.ts` (`Native CLI sprint 02 contract`).
- Unidade nativa (quando o runtime nativo cresce): `tests/unit/runtime_contract_runner.cpp`.

## 8. Referencias

- `.specs/product/VISION.md` (Runtime modes)
- `.specs/product/DOMAIN.md` (memory tier matrix)
- `.specs/architecture/ADR-002-runtime-boundaries-and-adapter-contract.md`
- `.specs/architecture/ADR-003-backend-selection-strategy.md`
- `.specs/runtime/CLI-CONTRACT.md`
