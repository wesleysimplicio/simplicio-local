# Goal Result

## Summary (sessao atual)

Auditoria completa da issue #81 (EPIC "runtime de inferencia nativa 10/10"):
nenhuma das 10 frentes declaradas era real de ponta a ponta no inicio da
sessao. Decompus a epic em 10 issues filhas honestas (#82-#91), cada uma
com veredito REAL/PARCIAL/SINTETICO e evidencia de codigo extraida da
auditoria (agente Explore dedicado).

Fechei 8 das 9 issues filhas trataveis nesta sessao, cada uma com PR
squash-merged em `main`, testes automatizados novos, e zero regressao nos
testes pre-existentes (a suite cresceu de 203 testes unitarios/16 E2E no
inicio para 222 unitarios/29 E2E no fim):

- #82 - oraculo de correcao real (compara contra referencia Python
  independente, nao mais escalar-vs-escalar).
- #83 - loader real de `.safetensors` (parser de header binario real,
  le bytes de tensores de verdade).
- #84 - tokenizer BPE real (parser JSON proprio + algoritmo BPE genuino,
  fallback explicito quando o modelo nao tem vocab/merges reais).
- #85 - forward denso real: `BuildTokenEmbedding`/`BuildOutputProjection`
  usam pesos reais quando disponiveis, cobrindo todos os adapters que
  compartilham `DenseAdapterBase::Generate`. Passou por duas rodadas de
  revisao adversarial (agents independentes de correcao C++ e seguranca)
  que encontraram e corrigiram, ANTES do merge: shape da projecao de saida
  transposto (nao batia com a convencao real HF/safetensors), flag de
  "pesos reais" global por asset em vez de por-chamada (bug de
  correcao real, nao cosmetico), quantizacao indevida de pesos reais,
  recursao sem limite no parser JSON (DoS por stack overflow), e
  underflow de `size_t` em offsets de tensor (alocacao absurda/crash).
- #87 - KV cache real: mesma saida com cache hit/miss sobre o forward real.
- #88 - MoE real: peso do expert roteado pelo router agora e de fato
  aplicado ao forward (nao so contabilidade de `Touch()`), religado no
  DeepSeek com fixture provando que a saida observada vem do expert
  selecionado, nao de um decoy da base.
- #89 - quantizacao int4/int8 validada sobre pesos reais, com tolerancia
  documentada.
- #90 - speculative decoding real: draft proposal vem de um forward
  autoregressivo genuino sobre um draft model real menor, nao mais
  copia+incremento do token autoritativo.
- #91 - `us4-cli serve --native`: servidor HTTP/1.1 real (sockets POSIX,
  sem dependencia nova) que responde OpenAI-compatible direto do
  `Generate()` do runtime, sem processo externo. Evidencia ponta-a-ponta:
  teste Playwright sobe o binario real e faz requisicao HTTP genuina.

**#86 (Metal/MLX/ANE reais) permanece aberta, bloqueada por ambiente**:
esta sessao roda em Linux x86_64 sem Metal/MLX, e por isso nao pode
implementar nem validar essa frente sem um runner macOS/Apple Silicon
real — reportar sucesso ali seria fabricar evidencia, o que os proprios
principios da epic proibem. Como consequencia, a epic #81 tambem
permanece aberta (seu DoD exige aceleracao real Metal/NEON e validacao em
CI macOS ARM64). Comentario detalhado deixado em #81 e #86 explicando
como retomar.

## Previous Summary (T11.5/T11.6)

T11.5 foi concluida. A evidencia de benchmark ANE foi ampliada no
`dense_baseline`: os casos `ane-requested` para Qwen e Llama ficam visiveis e
cada caso passa a registrar mixed-dispatch, contadores ANE e estado termico. Em
host nao-M5, a saida esperada e fallback observavel.

T11.6 foi concluida. Foi adicionada cobertura Playwright para garantir que
`--backend ane` em host nao elegivel exponha fallback explicito e mantenha o
mixed dispatch desabilitado.

## Previous Summary

T11.3 e T11.4 foram concluidas. O runtime agora tem um coordenador explicito
de mixed dispatch entre Metal e ANE, alem de um `ThermalMonitor` que aplica
downgrade de modo sob pressao termica derivada do probe. O estado nativo e o
CLI projetam estrategia mixed-dispatch, atividade ANE e sinais termicos sem
esconder fallback.

## Changed Files

- runtime/ane/mixed_dispatch.h
- runtime/ane/mixed_dispatch.cpp
- runtime/adapters/dense_adapter_base.cpp
- runtime/core/runtime_context.h
- runtime/core/runtime_context.cpp
- runtime/core/ius4v6_adapter.h
- apps/cli/main.cpp
- tests/unit/runtime_acceleration_contract_test.cpp
- tests/unit/runtime_contract_runner.cpp
- runtime/tuning/thermal_monitor.h
- runtime/tuning/thermal_monitor.cpp
- runtime/tuning/README.md

## Validation Commands

```bash
npm run lint
npm test -- --coverage
npm run pack:dry
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
npx playwright test --reporter=list,html tests/e2e/us4-cli.spec.ts
build\runtime\benchmarks\dense_baseline.exe
```

## Validation Results

- build: pass
- tests: pass
- lint: pass
- e2e: pass

## Remaining Risks

- T11.5-T11.6 ainda seguem pendentes no planejamento local.
- Sprint 12 segue como proximo bloco de issues abertas.
- A fonte termica atual e `probe-derived`; leitura real de IOPMrootDomain/powermetrics fica como aprofundamento Apple-host.

## Suggested PR Title

`feat(ane): add mixed dispatch and thermal monitor`

## Suggested PR Body

```md
## Summary
- add mixed Metal/ANE dispatch coordinator and runtime integration
- add probe-derived thermal monitor with explicit downgrade semantics
- expose mixed dispatch and thermal telemetry in native generation results and CLI
- cover ANE-eligible, metal-fallback, and thermal downgrade plans in native contract tests

## Validation
- [x] lint
- [x] unit and regression
- [x] native build and ctest
- [x] Playwright CLI E2E
- [x] pack dry-run

## Risks
- ANE benchmark evidence and graceful fallback slices still remain for Sprint 11
```
