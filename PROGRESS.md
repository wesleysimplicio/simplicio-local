# Progress Log

## Current Status

Sprint 08 em execucao continua. T08.3 ja mergeada no `main`; T08.4 fechada no
working tree e em validacao final para PR/merge.

## Checkpoints

### Checkpoint 1

Status: done

Task:
T08.3 - Deepen deepseek moe adapter

Result:
DeepSeek agora deriva logits do prompt/manifesto, materializa a assinatura
`moe-route eX eY`, e expõe reuse/eviction do `ExpertPager` de forma visivel no
output nativo e no CLI.

Validation:
`npm run lint`; `npm test -- --coverage`; `cmake --build build --config Release`;
`ctest --test-dir build --output-on-failure -C Release`;
`npx playwright test --reporter=list,html`; `npm run pack:dry`;
`build\\runtime\\benchmarks\\dense_baseline.exe`

Next:
T08.4 - replicar o mesmo nivel de concretude no Kimi e seguir para T08.5.

### Checkpoint 2

Status: in_progress

Task:
T08.4 - Deepen kimi moe adapter

Result:
Kimi ja consome `RouterDecision`, injeta `kimi-route eX eY`, mostra reuse do
pager no mesmo `RuntimeContext`, e ganhou cobertura unit + E2E dedicada.

Validation:
`npm run lint`; `npm test -- --coverage`; `cmake --build build --config Release`;
`ctest --test-dir build --output-on-failure -C Release`;
`npx playwright test --reporter=list,html`; `npm run pack:dry`;
`build\\runtime\\benchmarks\\dense_baseline.exe`

Next:
Fechar PR/merge de T08.4 e seguir para T08.5 (loader MoE shard-aware).

### Checkpoint 3

Status: in_progress

Task:
T08.5 - Add moe shard-aware loader contract

Result:
`ModelAsset` agora preserva shard metadata (`moe_lazy_load`,
`moe_active_experts`, `expertShardPaths`) e o CLI nativo projeta isso como
`moe_shard_count`, `moe_active_experts` e `moe_lazy_load`.

Validation:
`npm run lint`; `npm test -- --coverage`; `cmake --build build --config Release`;
`ctest --test-dir build --output-on-failure -C Release`;
`npx playwright test --reporter=list,html`; `npm run pack:dry`;
`build\\runtime\\benchmarks\\dense_baseline.exe`

Next:
Fechar PR/merge de T08.5 e seguir para T08.6 (telemetria MoE expandida).

### Checkpoint 4

Status: in_progress

Task:
T08.6 - Expand moe telemetry surface

Result:
O CLI nativo e o benchmark baseline agora expõem `moe_hit_rate`,
`moe_eviction_rate` e `moe_router_entropy`, enquanto `TelemetrySnapshot`
ganhou helpers semânticos para presença/hit/eviction de MoE.

Validation:
`npm run lint`; `npm test -- --coverage`; `cmake --build build --config Release`;
`ctest --test-dir build --output-on-failure -C Release`;
`npx playwright test --reporter=list,html`; `npm run pack:dry`;
`build\\runtime\\benchmarks\\dense_baseline.exe`

Next:
Fechar PR/merge de T08.6 e encerrar a issue #20 antes de seguir para Sprint 09.

## Blockers

Nenhum bloqueio funcional. O ambiente local continua sem GTest instalado, entao
os gates nativos seguem por `us4_runtime_smoke_test` e
`us4_runtime_contract_runner`.

## Validation History

| Command | Result | Notes |
|---|---|---|
| `npm run lint` | pass | JS starter ok |
| `npm test -- --coverage` | pass | 13 testes verdes |
| `cmake --build build --config Release` | pass | rebuild nativo ok |
| `ctest --test-dir build --output-on-failure -C Release` | pass | smoke + contract runner |
| `npx playwright test --reporter=list,html` | pass | 16 testes verdes na rodada atual |
| `npx playwright test --reporter=list,html` | pass | 17 testes verdes com loader MoE shard-aware |
| `npx playwright test --reporter=list,html` | pass | 17 testes verdes com telemetria MoE expandida |
| `npm run pack:dry` | pass | tarball `0.1.27` ok |
| `build\\runtime\\benchmarks\\dense_baseline.exe` | pass | observabilidade MoE/low-bit ok |
