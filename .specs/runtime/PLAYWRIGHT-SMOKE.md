# Playwright CLI Smoke Coverage

> Origem: Sprint 01 / T01.7. Define o escopo, os alvos e as evidencias minimas
> que o smoke E2E de Playwright deve produzir desde a primeira sprint, ainda na
> fase planning/bootstrap.

## 1. Escopo

- Runner: Playwright Test (`@playwright/test`).
- Config: `playwright.config.ts` na raiz do repo.
- Spec principal: `tests/e2e/us4-cli.spec.ts`.
- Alvo na fase atual: `node bin/cli.js` (CLI starter).
- Alvo aditivo quando existir: binario nativo `build/.../us4-cli` (suite native).
- Coverage do smoke nao depende de inferencia real.

## 2. Alvos obrigatorios da Sprint 01

Ordem fixa por contrato:

1. **`--version`** (primeiro alvo)
   - texto: stdout eh exatamente a versao;
   - JSON: payload contem `cli` e `version`.
2. **`--probe`** (segundo alvo)
   - texto: linhas com `mode:`, `platform:`, `memory:`;
   - JSON: bloco `probe` + bloco `mode` conforme `.specs/runtime/CLI-CONTRACT.md`.

Alvos adicionais ja cobertos hoje (nao podem regredir):

- `--mode auto --json` mantem o mesmo schema do probe JSON com taxonomia
  canonica de modos.

## 3. Variante nativa

Quando o binario nativo `us4-cli` existir em
`build/{apps,Release,}/us4-cli{,.exe}`, a suite native eh executada
automaticamente; ate la, ela eh `test.skip`. Esse comportamento eh proposital:
o smoke nunca deve falhar so porque o runtime ainda nao foi construido.

A suite native exercita o mesmo contrato JSON, adicionando assercoes sobre
campos de aceleracao (`metal_device`, `metal_queue_label`,
`metal_threads_per_group`, `metal_init_stage`, `has_mlx`, `has_metal`,
`has_neon`, etc.).

## 4. Evidencia minima exigida

A cada execucao, o smoke precisa produzir:

- `playwright-report/index.html`
- `test-results/results.json`
- `test-results/results.xml`
- attachments `stdout-*` e `stderr-*` por caso de teste
- pelo menos um attachment `trace` apontando para `trace.zip`

O gate de DoD (`.github/workflows/dod.yml`) bloqueia merge se qualquer um
desses artefatos faltar.

## 5. Coleta de evidencia adicional por caso

- Screenshot e video sao habilitados quando o test redo for executado
  (`retain-on-failure`).
- `testInfo.attach('stdout-*', ...)` eh obrigatorio em qualquer caso novo que
  invoque o CLI: garante diagnostico mesmo quando a assercao falha.

## 6. Princiios do smoke

- **Determinismo > cobertura**: o smoke testa contrato, nao comportamento de
  modelo.
- **Sem dependencia externa**: nao baixa pesos, nao chama rede.
- **Custo barato**: smoke completa em segundos no runner.
- **Honesto**: se um campo nao existe ainda, o smoke nao mente — o caso fica
  `test.skip` com motivo legivel.

## 7. Adicionando um novo caso

1. Confirma o contrato em `.specs/runtime/CLI-CONTRACT.md` antes de escrever
   assercoes.
2. Cria o caso em `tests/e2e/us4-cli.spec.ts` na suite apropriada (`starter` ou
   `native`).
3. Anexa stdout e stderr via `attachCommand`/`testInfo.attach`.
4. Confirma localmente: `npx playwright test --reporter=list,html`.
5. Confirma evidencia: `playwright-report/index.html` + `test-results/`.

## 8. Quando o smoke deixa de ser smoke

Apos a fase inference-capable existir, a suite Playwright deve ser expandida
com fluxos de `run`, `serve`, `bench`, e `tune` em testes separados, mantendo
este smoke como porta de entrada de contrato. Esta evolucao ocorre no `T07.x`
e em `runtime/benchmarks/`.

## 9. Referencias

- `.specs/runtime/CLI-CONTRACT.md`
- `.specs/runtime/HARDWARE-PROBE.md`
- `tests/e2e/README.md`
- `tests/e2e/us4-cli.spec.ts`
- `.github/workflows/dod.yml`
