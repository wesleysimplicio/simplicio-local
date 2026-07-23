# Metodologia de benchmarks e qualidade

Esta metodologia é o contrato da issue #126. Ela separa medição de desempenho,
perplexity e evals de sanidade. Templates, dry-runs e fixtures provam a máquina
de medir; somente receipts de checkpoint real provam desempenho ou qualidade.

## Identidade da execução

Cada captura deve registrar:

- SHA do código e hashes SHA-256 do manifesto, corpus, binário, `config.json` e
  artefatos de conversão;
- família, revisão exata do checkpoint e configuração de quantização;
- sistema operacional, arquitetura, versão do Python e comando executado;
- CPU, RAM, armazenamento e filesystem para resultados de desempenho;
- variáveis que alteram o runtime, especialmente perfil, cache de experts,
  `TOPP`, `TOPK`, `MTP`, `DSA`, `DIRECT`, threads e limites de memória.

Não publique caminhos locais, tokens, prompts privados ou o ambiente completo.

## Corpus e perplexity

O corpus real é JSONL UTF-8 imutável, uma linha por documento:

```json
{"id":"documento-0001","text":"texto do corpus"}
```

Fixe e publique o arquivo normalizado e seu SHA-256. A mesma família e revisão
de tokenizer devem ser usadas em todas as variantes. Não compare perplexities
produzidas por tokenizers ou segmentações diferentes.

O runner usa teacher forcing do modo `SCORE` do motor. Para cada documento com
tokens \(t_0,\ldots,t_n\), prediz \(t_1,\ldots,t_n\), soma a log-probabilidade
observada e calcula:

\[
\mathrm{PPL}=\exp\left(-\frac{\sum_i \log p(t_i\mid t_{<i})}{N}\right)
\]

`N` é o total de tokens efetivamente preditos, não o número de documentos.
Resultados com linhas ausentes, contagem divergente, NaN, infinito, retorno
não-zero ou hash divergente falham. Métricas ficam `null` com motivo.

Execute, no mínimo, bf16-oráculo, int4 uniforme e o dtype-map misto do perfil
16 GB. Cada família disponível recebe manifesto e receipt próprios. O arquivo
`perplexity-smoke.token_ids.jsonl` existe apenas para testar o contrato; tokens
arbitrários não medem qualidade linguística.

## Evals de sanidade

Use subconjuntos fixos e hashados de 50 itens de MMLU-mini e HellaSwag-mini.
Registre seed, IDs e normalização. Rode todas as variantes do mesmo manifesto
com `engine/c/tools/eval_glm.py`. Publique accuracy e accuracy normalizada como
sanidade, não como ranking. Dataset ausente, tokenizer ausente ou quantidade
menor que a declarada é falha, não skip silencioso.

## Desempenho

Use o mesmo host, checkpoint, prompt tokenizado, número de tokens gerados,
threads e limites em toda comparação.

- Faça uma execução de aquecimento que não entra na agregação.
- Faça no mínimo cinco execuções medidas e publique cada receipt.
- Agregue pela mediana; mantenha mínimo, máximo e dispersão disponíveis.
- `prefill tok/s` conta tokens do prompt divididos pelo prefill.
- `decode tok/s` exclui prefill e conta somente tokens emitidos.
- RSS é o pico observado do processo.
- GB lidos/token usa bytes físicos observados divididos por tokens emitidos.
- Hit-rate é `hits / (hits + misses)`; denominador zero produz `null`.
- Acceptance MTP usa tokens aceitos sobre tokens propostos.

### Cache frio e quente

`frio` significa que o operador realizou e registrou um procedimento explícito
antes da execução. O harness nunca executa comandos privilegiados nem afirma
ter limpado page cache. Reinício controlado ou limpeza documentada pelo operador
são aceitos; apenas marcar `DROP=1` não prova cache físico frio.

`quente` significa repetições consecutivas sem limpeza, após uma execução de
aquecimento. Registre pressão de memória, swap e temperatura. Throttling, swap
storm ou OOM invalidam claim de throughput, mas o receipt da falha é preservado.

## Regressão da fixture 313M

A fixture 313M é sintética. Compare somente com baseline gerado pelo mesmo
binário de benchmark, host e modo. O gate local usa tolerância de ±10% e deve
falhar se identidade, unidade, amostra ou baseline estiverem ausentes. Nunca
promova esse resultado a desempenho do modelo real.

## Comparativa llama.cpp

Na mesma máquina, rode um modelo documentado que caiba em 16 GB com revisão,
quantização, contexto, prompt e limites fixos. Publique comando e receipt bruto.
A comparação deve declarar que os modelos diferem em tamanho/capacidade; ela
mostra custo operacional local, não equivalência de qualidade.

## O que não medimos

- hardware não disponível;
- energia sem medidor calibrado;
- qualidade de corpus ou checkpoint não executado;
- desempenho extrapolado de fixture;
- equivalência entre famílias, tokenizers ou modelos distintos.

README e material de divulgação só podem citar números presentes em receipts
versionados que satisfaçam esta metodologia.
