# Baseline real GLM-5.2 int4 em host 16 GB (#118)

Status: **BLOCKED — aguarda host 16 GB, checkpoint real e execução da matriz.**

Este documento é o destino canônico do relatório. Nenhum valor abaixo foi
medido neste checkout. O runner preserva valores não observáveis como `null`
com motivo; não substitua esses campos por estimativas.

## Artefatos versionados

- Prompts: `docs/baselines/glm52-16gb-prompts.json`
- Schema: `docs/baselines/glm52-16gb-capture.schema.json`
- Runner: `scripts/capture_glm52_16gb_baseline.py`
- Testes: `tests/baselines/test_capture_glm52_16gb_baseline.py`

## Uso no host de medição

O runner não baixa pesos, não limpa page cache e não executa comandos
privilegiados. O checkpoint precisa estar pronto antes do `prepare`.

```bash
python3 scripts/capture_glm52_16gb_baseline.py prepare \
  --model-dir /path/to/GLM-5.2-colibri-int4 \
  --output-dir out/glm52-16gb
```

`prepare` falha fechado quando:

- a memória física/efetiva não está entre 15 e 17 GiB;
- `config.json`, `tokenizer.json` ou os shards não existem;
- os shards somam menos de 300 GB (proteção contra fixture promovida);
- a configuração não tem escala compatível com GLM-5.2 ou não há evidência
  da cabeça MTP int8;
- o motor não está compilado;
- o worktree de origem está sujo;
- `coli plan --json` ou `coli doctor --json` não aprovam o perfil.

Um `doctor` reprovado ou um gate de RSS reprovado deve permanecer no receipt:
é um resultado `does_not_run`, não uma medição a ser descartada.

Liste os casos e execute um por vez:

```bash
python3 scripts/capture_glm52_16gb_baseline.py list-cases \
  --session out/glm52-16gb/session.json

python3 scripts/capture_glm52_16gb_baseline.py run-case \
  --session out/glm52-16gb/session.json \
  --case baseline-short-cold-1 \
  --cold-cache-attestation "host rebooted immediately before this case"
```

Casos `cold` exigem uma declaração explícita. O operador deve reiniciar o host
ou limpar caches segundo a política local; o runner deliberadamente não usa
`sudo purge`, `drop_caches` ou equivalentes. Os casos quentes são três
repetições por prompt. As variações controladas usam o prompt médio, três
repetições cada:

- baseline: `TOPP=0` (top-k fixo), `MTP=0`, `DIRECT=0`;
- `topp-0.7`: `TOPP=0.7`;
- `mtp-on`: `MTP=1`;
- `direct-on`: `DIRECT=1`.

Finalize somente após executar a matriz:

```bash
python3 scripts/capture_glm52_16gb_baseline.py finalize \
  --session out/glm52-16gb/session.json

python3 scripts/capture_glm52_16gb_baseline.py validate \
  --session out/glm52-16gb/session.json
```

## Metodologia e interpretação

Cada receipt inclui SHA do commit, identidade do checkpoint sem hashear
centenas de GB de conteúdo (hash determinístico de nomes e tamanhos, além de
hash integral de config/tokenizer/manifest), host, filesystem, argv, ambiente,
horários, código de saída e hashes dos logs.

O parser captura token count, throughput de decode, RSS reportado pelo motor,
hit-rate e tokens produzidos. Métricas que o motor/SO não expõem de forma
confiável, como throughput de prefill separado, bytes físicos de disco por
token ou temperatura sem `smartctl`, permanecem `null` com motivo. O veredito
fica `incomplete` enquanto uma métrica obrigatória estiver ausente.

Regras de veredito:

- `runs`: matriz completa, métricas obrigatórias observáveis, sem swap e sem
  falha;
- `runs_degraded`: matriz completa e saída gerada, mas houve swap;
- `does_not_run`: preflight bloqueado ou caso obrigatório falhou;
- `incomplete`: casos/evidências/métricas faltantes.

## Resultados

Ainda não medidos:

| Campo | Valor |
|---|---:|
| Hardware e SO | `null` |
| Checkpoint/manifest | `null` |
| `plan` / `doctor` | `null` |
| Frio e quente (3×) | `null` |
| Prefill/decode tok/s | `null` |
| RSS pico | `null` |
| Hit-rate | `null` |
| GB lidos/token | `null` |
| Swap | `null` |
| Temperatura SSD | `null` |
| Efeito `TOPP=0.7` | `null` |
| Efeito MTP on/off | `null` |
| Efeito DIRECT on/off | `null` |
| Veredito | `incomplete` |

Limitações atuais: macOS/Apple Silicon, host 16 GB e checkpoint GLM-5.2 real
não foram disponibilizados nesta sessão.
