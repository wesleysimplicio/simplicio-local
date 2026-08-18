# Benchmark: jogo de damas com Qwen3.8 + llama.cpp TurboQuant

> Captura real em 2026-08-18T11:18:00.633Z. Os números abaixo foram medidos; campos sem exposição do provedor permanecem como —.

## Resultado

- Status: **captured**
- Jogo: regras locais executadas e 3 jogada(s) preta(s) solicitada(s) ao modelo.
- Jogadas do modelo legais: **3/3**.
- Fallback local: **0/3**.
- Todos os gates do motor e da página foram executados separadamente.

## Ambiente

| Campo | Valor |
|---|---|
| Host | linux / x64 |
| CPU | Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz |
| CPUs lógicas | 9 |
| RAM total | 21.93 GiB |
| RAM disponível antes | 18.52 GiB |
| Swap total | 0.00 GiB |
| Node | v24.19.0 |
| Simplicio | 3.8.13 (SHA-256 `6df309002e6e1243668de64d696ec22b8bffa42cd5b9d103a0e06269ef1e6a43`) |

## Backend e modelo

| Campo | Valor |
|---|---|
| Backend efetivo | llama-cpp-turboquant |
| Release Atomic | b10269-1.4.0 |
| Asset | llama-turboquant-linux-x64-vulkan.tar.gz |
| llama-server | version: b10269-1.4.0 (build 10679, commit 074bf826e) built with GNU 11.4.0 for Linux x86_64 |
| SHA-256 do executável | 10fa6d72b06742d207836a31bce90d51c96c1a44d90e21c7f3018412c599a2dc |
| Modelo | Qwen3.8-27B-Q4_K_M.gguf |
| Quantização | Q4_K_M |
| Tamanho | 15.93 GiB |
| SHA-256 do modelo | 7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169 |
| Contexto | 512 |
| Threads / batch | 9 / 9 |
| KV K / V | turbo3 / turbo3 |
| Flash Attention | auto |
| KV unified | true |

## Latência e tokens do Qwen

Tempo de prontidão inclui o carregamento do modelo pelo servidor. A tabela é a
agregação medida, sem contar a chamada de aquecimento.

| Rep. | Request ms | Tokens in | Cache read | Tokens out | Tokens total | TTFT/prompt ms | Decode ms | In tok/s | Out tok/s | Jogada | Legal | Fallback |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|:---:|:---:|
| 1 | 45937.23 | 226 | 0 | 9 | 235 | 37756.73 | 5579.24 | 5.99 | 1.61 | b6-a5 | sim | não |
| 2 | 38848.17 | 196 | 21 | 9 | 205 | 28187.75 | 7248.97 | 6.95 | 1.24 | d6-b4 | sim | não |
| 3 | 42001.85 | 236 | 21 | 9 | 245 | 32487.40 | 5056.91 | 7.26 | 1.78 | f6-e5 | sim | não |

| Agregado | Valor |
|---|---:|
| Prontidão do llama-server | 96973.79 ms |
| Aquecimento | 9957.83 ms |
| Requests medidos | 3 |
| Soma tokens in | 658 |
| Soma cache read | 42 |
| Soma tokens out | 27 |
| Soma tokens total | 685 |
| Mediana request | 42001.85 ms |
| Mediana TTFT/prompt | 32487.40 ms |
| Mediana decode | 5579.24 ms |
| Mediana input tok/s | 6.95 |
| Mediana output tok/s | 1.61 |

## Recursos do processo llama-server

| Métrica | Valor |
|---|---:|
| Pico RSS observado | 18.36 GiB |
| Pico virtual observado | 30.66 GiB |
| Swap no último sample | 0.00 MiB |
| Read bytes delta | 69.29 MiB |
| Write bytes delta | 0.02 MiB |
| Minor / major page faults | 636793 / 39 |
| CPU time delta | 938540 ms |
| Medição térmica/energia | — (sem sensor/medidor calibrado disponível) |

## Gates

- Motor: node --test tests/checkers_engine.test.mjs tests/checkers_static.test.mjs.
- Sintaxe: node --check apps/checkers/checkers.js.
- Página: arquivos estáticos servidos por HTTP; teste de integridade dos controles concluído.
- O download do Chromium do Playwright foi tentado, mas o CDN respondeu erro de certificado/502; portanto não há claim de browser E2E nesta captura.

## Reprodutibilidade

```bash
python3 -m http.server 4173 --directory apps/checkers
node scripts/benchmark-checkers.mjs --repetitions 3
```

Flags usadas no servidor: --cache-type-k turbo3 --cache-type-v turbo3
--flash-attn auto --kv-unified --ctx-size 512
--threads 9 --threads-batch 9
--parallel 1 --reasoning off --metrics --no-webui.

## Limitações

- O host é CPU-only; esta captura prova integração real com o fork Atomic e o
  caminho TurboQuant em CPU, não throughput GPU.
- Tokens de raciocínio, cache hit, rede física e energia só são publicados se o
  servidor os expuser ou houver medidor apropriado; não foram inferidos.
- A jogada é considerada do Qwen somente quando a saída textual corresponde a
  uma jogada legal do estado atual. Fallbacks ficam explícitos.
