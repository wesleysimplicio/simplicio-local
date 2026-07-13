# Breakdown tensor-a-tensor do tronco denso (issue #119, epica #116)

## Aviso honesto sobre a origem dos numeros (leia antes do resto)

**Estes numeros vem de uma fixture SINTETICA (313M parametros, pesos
aleatorios), gerada localmente por `engine/c/tools/make_glm_bench_model.py`
— NAO do checkpoint GLM-5.2 real (~370 GB).** O checkpoint real e' baixado
sob demanda de `zai-org/GLM-5.2-FP8` e nao esta' disponivel no ambiente
onde este trabalho foi feito (sandbox sem acesso a 370 GB de disco/rede
sustentada). A validacao de RSS em hardware real de 16 GB e' rastreada
separadamente na issue #118 (bloqueada por hardware) e permanece pendente.

O que ESTES numeros provam: o mecanismo de instrumentacao (`DUMP_TENSORS=1`)
funciona corretamente, emite uma tabela tensor-a-tensor completa e correta
(nome, shape, dtype, bytes residentes), e as PROPORCOES entre categorias de
tensor (embed/lm_head vs attention vs dense-mlp vs shared-expert vs
indexer/router/normas) devem generalizar qualitativamente para o GLM-5.2 real,
porque a fixture usa a MESMA arquitetura `glm_moe_dsa` (so' em escala menor:
8 camadas em vez de 78+1 MTP, hidden=1024 em vez de muito maior, 32 experts
routed em vez de 256). Os valores ABSOLUTOS de bytes NAO devem ser
extrapolados linearmente para o modelo real sem medir o modelo real.

## Como reproduzir

```bash
cd engine/c
make glm
python3 tools/make_glm_bench_model.py --output /tmp/glm_bench_medium --device cpu
DUMP_TENSORS=1 SNAP=/tmp/glm_bench_medium TF=1 ./glm 8 16 16   # fp32 (dbits=ebits=16)
DUMP_TENSORS=1 SNAP=/tmp/glm_bench_medium TF=1 ./glm 8 4 4     # int4 (dbits=ebits=4)
```

A fixture (`bench_manifest.json`) documenta o proprio disclaimer:

```json
{
  "seed": 1234,
  "parameters": 312955392,
  "parameters_billions": 0.313,
  "purpose": "backend benchmark fixture; random weights, not a language model"
}
```

## Mecanismo: `DUMP_TENSORS=1`

Implementado em `engine/c/glm.c` (`dump_tensor_row`, chamada de dentro de
`qt_load` e `ld`, gate `g_dump_tensors`). Quando ativo, cada tensor carregado
emite uma linha em stdout:

```
[DUMP_TENSORS] <nome>  shape=[O,I] dtype=<F32|I8|I4|I2> bytes=<N>
```

seguida de um total agregado ao fim do load. Custo zero quando desativado
(um `if` por tensor, nenhuma alocacao extra). Redirecione stdout para um
arquivo se quiser persistir a tabela (`DUMP_TENSORS=1 ... ./glm ... >
tensors.log`).

## Resumo por categoria — fixture 313M, `--dbits 16 --ebits 16` (fp32, sem quantizacao)

Total residente: **245.19 MB** (245189120 bytes)

| categoria                          | tensores | bytes       | %      |
|-------------------------------------|---------:|------------:|-------:|
| dense_mlp (first_k_dense_replace)   |        9 |  75.50 MB   |  30.8% |
| attention (MLA)                     |       56 |  68.17 MB   |  27.8% |
| embed + lm_head                     |        2 |  67.11 MB   |  27.4% |
| shared_expert                       |       15 |  31.46 MB   |  12.8% |
| dsa_indexer                         |       39 |   2.23 MB   |   0.9% |
| router (gate + bias)                |       10 |   0.66 MB   |   0.3% |
| normas (input/post/final)           |       17 |   0.07 MB   |   0.0% |

## Resumo por categoria — fixture 313M, `--dbits 4 --ebits 4` (int4)

Total residente: **31.61 MB** (31613184 bytes) — fator de compressao ~7.76x
sobre fp32, consistente com o esperado (4 bits vs 32 bits + overhead de
escala por linha).

| categoria                          | tensores | bytes       | %      |
|-------------------------------------|---------:|------------:|-------:|
| dense_mlp (first_k_dense_replace)   |        9 |   9.50 MB   |  30.0% |
| attention (MLA)                     |       56 |   8.69 MB   |  27.5% |
| embed + lm_head                     |        2 |   8.45 MB   |  26.7% |
| shared_expert                       |       15 |   3.97 MB   |  12.6% |
| router (gate + bias)                |       10 |   0.66 MB   |   2.1% |
| dsa_indexer                         |       39 |   0.27 MB   |   0.9% |
| normas (input/post/final)           |       17 |   0.07 MB   |   0.2% |

Nota: `router` e `normas` ficam SEMPRE em f32 no motor (sao pequenos e
sensiveis, ver comentario em `convert_fp8_to_int4.py::classify`) — por isso
seu peso RELATIVO cresce quando o resto do tronco encolhe com a
quantizacao.

## Amostra de linhas cruas (fp32) — primeiras camadas

```
[DUMP_TENSORS] model.embed_tokens.weight                       shape=[8192,1024] dtype=F32 bytes=33554432
[DUMP_TENSORS] lm_head.weight                                  shape=[8192,1024] dtype=F32 bytes=33554432
[DUMP_TENSORS] model.norm.weight                                shape=[1024,1]   dtype=F32 bytes=4096
[DUMP_TENSORS] model.layers.0.input_layernorm.weight            shape=[1024,1]   dtype=F32 bytes=4096
[DUMP_TENSORS] model.layers.0.post_attention_layernorm.weight   shape=[1024,1]   dtype=F32 bytes=4096
[DUMP_TENSORS] model.layers.0.self_attn.q_a_proj.weight         shape=[256,1024] dtype=F32 bytes=1048576
[DUMP_TENSORS] model.layers.0.self_attn.q_a_layernorm.weight    shape=[256,1]    dtype=F32 bytes=1024
[DUMP_TENSORS] model.layers.0.self_attn.q_b_proj.weight         shape=[1536,256] dtype=F32 bytes=1572864
[DUMP_TENSORS] model.layers.0.self_attn.kv_a_proj_with_mqa.weight shape=[160,1024] dtype=F32 bytes=655360
[DUMP_TENSORS] model.layers.0.self_attn.kv_a_layernorm.weight   shape=[128,1]    dtype=F32 bytes=512
[DUMP_TENSORS] model.layers.0.self_attn.kv_b_proj.weight        shape=[2048,128] dtype=F32 bytes=1048576
[DUMP_TENSORS] model.layers.0.self_attn.o_proj.weight           shape=[1024,1024] dtype=F32 bytes=4194304
[DUMP_TENSORS] model.layers.0.mlp.gate_proj.weight              shape=[2048,1024] dtype=F32 bytes=8388608
[DUMP_TENSORS] model.layers.0.mlp.up_proj.weight                shape=[2048,1024] dtype=F32 bytes=8388608
[DUMP_TENSORS] model.layers.0.mlp.down_proj.weight              shape=[1024,2048] dtype=F32 bytes=8388608
```

(camadas 0-2 sao densas nesta config — `first_k_dense_replace=3` — camadas
3-7 sao sparse: router + shared_expert + experts routed em streaming, que
`DUMP_TENSORS` NAO lista porque nao residem — sao paginados do disco por
`expert_load`, fora do orcamento "tronco denso residente".)

## O que isto implica para o GLM-5.2 real (extrapolacao qualitativa, nao medida)

- `embed+lm_head` e `attention (MLA)` sao fracoes GRANDES do tronco denso
  (juntos ~55% em fp32 nesta fixture). Sao os melhores candidatos a
  quantizacao mista mais agressiva (int2 via `--dtype-map`, ver
  `docs/profiles/16gb.md`) porque sao residentes o tempo todo e nao ficam no
  caminho critico de qualidade linha-a-linha da mesma forma que os experts
  routed (que ja tem sua propria banda de erro tolerada pelo roteamento).
- `router` e normas devem continuar em f32 (pequenos, sensiveis) — nao vale
  a pena quantiza-los mesmo sob pressao extrema de memoria.
- Medir os valores absolutos exatos do GLM-5.2 real (~9.9 GB em int4 no
  tronco denso, conforme documentado no upstream do colibri) fica pendente
  de acesso ao checkpoint real ou de uma maquina com disco/rede suficientes
  para baixa-lo — nao feito nesta issue.
