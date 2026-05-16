# CLI Contract - `us4-cli`

> Origem: Sprint 01 / T01.2. Define o contrato de output do CLI `us4-cli` para
> os fluxos smoke `--version` e `--probe`. Este documento eh normativo: testes
> Playwright (`tests/e2e/us4-cli.spec.ts`) e CI do DoD validam o formato aqui.

## 1. Escopo

- Cobre apenas os fluxos smoke obrigatorios da Sprint 01:
  - `--version`
  - `--probe`
  - `--mode <value>` (subset usado no smoke)
- Outros subcomandos (`run`, `list-models`, `serve`, `bench`, `tune`) tem seus
  proprios contratos em sprints futuras.

## 2. Regras gerais

- Toda flag suporta saida texto (default) e JSON (`--json`).
- JSON eh sempre uma unica linha terminada com `\n` (single-line, parseable).
- Texto eh humano-leitor, sem cor, sem table-art ASCII, sem timestamps.
- Exit code `0` para sucesso; nao-zero para falha de contrato (uso invalido,
  flag desconhecida, recurso indisponivel).
- `stderr` fica vazio em caminho feliz. Diagnostico vai pra stderr; payload de
  contrato vai pra stdout.

## 3. `--version`

### Texto

- Exatamente uma linha.
- Conteudo: a versao do CLI (mesmo valor que `package.json#version` na fase
  starter, e que o runtime nativo na fase de runtime).

Exemplo:

```text
0.4.0
```

### JSON (`--version --json`)

Campos obrigatorios:

```json
{
  "cli": "us4-cli",
  "version": "<semver>"
}
```

- `cli`: literal `"us4-cli"`.
- `version`: semver string.

## 4. `--probe`

### Texto

- Multi-linha, human-readable.
- Primeira linha contem `us4-cli <version>`.
- Linhas subsequentes contem pares `<chave>: <valor>` (uma por linha) cobrindo
  pelo menos:
  - `mode: <selected-mode>`
  - `platform: <darwin|linux|win32|...>`
  - `memory: <human-readable>`

### JSON (`--probe --json`)

Estrutura minima obrigatoria:

```json
{
  "cli": "us4-cli",
  "version": "<semver>",
  "probe": {
    "platform": "<string>",
    "arch": "<string>",
    "cpuModel": "<string>",
    "logicalCores": <number>,
    "totalMemoryBytes": <number>,
    "totalMemoryGiB": <number>,
    "appleSilicon": <boolean>,
    "aneEligible": <boolean>
  },
  "mode": {
    "requested": "auto",
    "selected": "<runtime-mode>",
    "taxonomy": ["FULL", "BALANCED_PLUS", "DEGRADED", "ULTRA_LOW", "MICRO", "MICRO_PLUS", "NANO"],
    "source": "memory-tier"
  }
}
```

Regras:

- `mode.taxonomy` mantem a ordem canonica dos sete modos.
- `mode.selected` deve estar em `mode.taxonomy`.
- `probe.appleSilicon=true` implica `probe.arch === "arm64"`.
- `probe.aneEligible=true` so eh valido em chips M5+ (opt-in).

### Variante nativa

Quando o binario nativo `us4-cli` existe, o probe JSON expande com campos de
runtime/aceleracao:

- `chip`, `has_mlx`, `has_metal`, `has_neon`, `neon_vector_bits`,
  `has_performance_cores`, `has_efficiency_cores`,
- `metal_device`, `metal_queue_label`, `metal_threads_per_group`,
  `metal_init_stage`, `metal_queue_created`,
  `metal_autorelease_boundary_requested`, `metal_objc_boundary_supported`,
  `metal_reason`,
- `supports_unified_memory`, `recommended_mode`.

Esses campos sao validados em `tests/e2e/us4-cli.spec.ts` na suite
`Native CLI sprint 02 contract`.

## 5. `--mode <value>`

### `--mode auto --json`

Mesma estrutura de `--probe --json`, mas `mode.requested` reflete a flag e
`mode.source` continua `"memory-tier"` quando a selecao foi automatica.

## 6. Texto vs JSON

- JSON eh a interface de programa (CI, testes, integracoes).
- Texto eh a interface humana.
- Mudanca de schema JSON eh **breaking change** e exige ADR + entrada em
  CHANGELOG.
- Mudanca de wording em texto exige atualizar somente `tests/e2e/` quando o
  assert depende da string.

## 7. Erros

- Flag desconhecida -> exit code `1`, `stderr` com mensagem curta.
- Combinacao invalida (ex.: `--mode invalido`) -> exit code `1`,
  `stderr` com mensagem explicando a taxonomia aceita.

## 8. Referencias cruzadas

- Sprint 01 task: `.specs/sprints/sprint-01/T01.2-cli-contract.task.md`
- Smoke E2E: `tests/e2e/us4-cli.spec.ts`
- Smoke unit: `test/cli.smoke.test.js`
- Modos: `.specs/product/VISION.md` secao "Runtime modes"
- Probe: `.specs/runtime/HARDWARE-PROBE.md`
