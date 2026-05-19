# Telemetry Skeleton and Maturity Gates

> Origem: Sprint 01 / T01.5. Define quais categorias de telemetria existem desde
> o dia 1 e quais portoes de qualidade se aplicam em cada fase. Mantem honestidade
> entre o que ja eh exigido agora e o que so faz sentido depois da inferencia
> real.

## 1. Categorias de telemetria

Categorias canonicas. Codigo nao deve inventar nomes paralelos.

| Categoria | Conteudo |
|---|---|
| `runtime.context` | adapter resolvido, modo, backend pedido vs observado, motivo do fallback |
| `runtime.session` | id de sessao, prompt size, tokens gerados, elapsed, seed |
| `backend.dispatch` | nome do op, backend, latencia, fallback events |
| `memory.alloc` | bytes alocados (cpu/unified/shared), high-water mark |
| `kv.lifecycle` | tier (hot/warm/cold/summary), hit/miss, page count, evict count |
| `moe.routing` | top-k chosen, expert hit-rate, eviction count, router entropy |
| `correctness.delta` | logit diff vs referencia, drift threshold, decisao do guard |
| `release.metadata` | versao, build hash, target arch, runner profile |

Todas as categorias devem incluir, sempre que aplicavel:

- `hardware_profile` (chip + tier de memoria),
- `adapter`,
- `backend`,
- `runtime_mode`.

## 2. Output

- Dev e CI: `TelemetrySink` faz log estruturado (JSON line por evento).
- Producao (futuro): export por arquivo (`telemetry.jsonl`) + plug opcional pra
  integradores via interface do `TelemetrySink`.
- Default eh **silencio observavel**: nenhuma categoria liga sozinha sem flag
  CLI ou env explicito.
- Nada de log de prompt completo ou pesos por default.

## 3. Gates por fase de maturidade

A validacao do projeto eh estratificada para nao prometer correctness antes da
inferencia existir.

### Fase planning/bootstrap (atual)

- doc consistency,
- starter self-tests (`npm test`),
- coverage starter >= 80% (`coverage/coverage-summary.json`),
- sprint/task completeness.

### Fase early runtime

- `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release`,
- `cmake --build build` sem warning novo,
- `ctest --test-dir build --output-on-failure` verde,
- Playwright smoke verde com evidencias (`playwright-report/`, `test-results/`),
- coverage de diff >= 80% para alvos cobertos.

### Fase inference-capable

- correctness fixture (`runtime/benchmarks/correctness/`) dentro de tolerancia,
- regression suite cumulativa verde,
- benchmark evidence (`hardware_profile`, `adapter`, `backend`, `runtime_mode`,
  `tokens`, `elapsed`, `text_fingerprint`),
- release gate (ver `.specs/workflow/RELEASE.md`).

Logit-diff so eh exigido **a partir da fase inference-capable**. Antes disso,
docs nao podem implicar que a regressao numerica ja eh enforced.

## 4. Telemetria por backend

Cada backend deve emitir:

- `requested_backend`,
- `observed_backend`,
- `backend_reason` (ex.: `auto-metal`, `auto-mlx`, `auto-neon`, `auto-scalar`),
- `fell_back` (boolean),
- `fallback_reason` (string curta).

Esses campos sao requisito do contrato CLI quando `--json` esta presente.

## 5. Telemetria por KV

A partir de Sprint 06 (`runtime/kv/`):

- `hit_hot`, `hit_warm`, `hit_cold`,
- `summarize_ratio`,
- `evict_count`,
- `prefix_cache_dedup_count`.

Antes de Sprint 06, KV emite somente `prompt_token_reuse` e `page_count`.

## 6. Telemetria por MoE

A partir de Sprint 08 (`runtime/moe/`):

- `expert_hit_rate`,
- `expert_eviction_count`,
- `router_entropy`,
- `prefetch_hit_ratio` (Sprint 09).

No contrato CLI/bench atual, isso aparece como:

- `moe_hit_rate`,
- `moe_eviction_rate`,
- `moe_router_entropy`.

## 7. Telemetria de correctness

A partir do primeiro adapter capaz de inferencia (Sprint 02 com fixtures de
referencia):

- `logit_l2`,
- `logit_max_abs`,
- `token_diff_count` em janela determinada,
- `drift_threshold`,
- `guard_decision` (`pass`, `warn`, `fail`).

## 8. Proibicoes

- nao acumular metricas em memoria sem limite (sempre buffered + flush);
- nao logar conteudo completo de prompt, output ou pesos;
- nao chamar telemetria de "metric" e "stat" simultaneamente para a mesma coisa;
- nao adicionar categoria nova sem PR + atualizacao deste arquivo.

## 9. Referencias

- `.specs/workflow/WORKFLOW.md` (validacao por maturidade)
- `.specs/workflow/RELEASE.md` (gating por fase)
- `.specs/architecture/PATTERNS.md` (logging/telemetry)
- `.specs/architecture/ADR-003-backend-selection-strategy.md`
