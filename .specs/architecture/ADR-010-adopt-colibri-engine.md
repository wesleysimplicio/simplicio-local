# ADR-010: Adotar o motor colibri (Apache-2.0) como engine tier deste repositório

---

## Status

`Aceito`

---

## Data

`2026-07-13`

---

## Autores

- us4-core

---

## Contexto

O objetivo de produto (`.specs/product/VISION.md`) inclui rodar modelos
tier-1 (DeepSeek, GLM, Kimi) em hardware modesto (ex.: 16GB de RAM, sem GPU),
aceitando latência alta em troca de viabilidade. O runtime C++ nativo em
`runtime/` (MLX + Metal + NEON/Accelerate, ver ADR-001, ADR-002, ADR-006)
ainda não cobre o forward MoE completo desses modelos ponta a ponta.

Uma auditoria de código identificou que o projeto `colibri`
(https://github.com/JustVugg/colibri, Apache-2.0) já implementa, em C puro,
exatamente essa capacidade: forward MoE completo (MLA attention, router
sigmoid `noaux_tc`, shared expert), streaming de experts do disco via
`pread` + `fadvise`, kernels quantizados int8/int4/int2 com dot inteiro
(AVX2/AVX-512-VNNI/NEON-SDOT), tokenizer BPE byte-level, KV cache
comprimido com persistência, speculative decoding lossless via MTP nativo,
e servidor OpenAI-compatible com SSE. Um fork mantido pelo owner do produto
(https://github.com/wesleysimplicio/colibri) serve como origem estável de
vendoring.

Reimplementar esse motor em C++ dentro do runtime nativo antes de ter um
baseline funcional adiaria a entrega de valor por vários sprints, e o
código C já é testado e funcional. A decisão aqui é *só* sobre como trazer
esse código para o repositório — não sobre substituir o runtime nativo.

ADRs relacionados: [ADR-001](./ADR-001-mlx-primary-backend.md) (MLX como
backend primário do runtime nativo), [ADR-002](./ADR-002-runtime-boundaries-and-adapter-contract.md)
(fronteiras do runtime), [ADR-006](./ADR-006-moe-expert-paging.md)
(paginação de experts no runtime nativo).

---

## Decisão

Vendorizamos o código C do colibri para dentro deste repositório, em
`engine/`, como uma **engine tier separada e paralela** ao runtime C++
nativo — não como substituição dele.

- Escopo: código-fonte de `c/` (glm.c, olmoe.c, headers, Makefile,
  backend_cuda, scripts Python de operação como doctor/resource_plan/
  openai_server, testes e ferramentas) vai para `engine/c/`. O frontend web
  (`web/`) vai para `apps/web-chat/` com README próprio. Nenhuma mudança
  funcional no motor é feita nesta issue.
- Atribuição Apache-2.0 é obrigatória: `engine/LICENSE` (cópia da licença
  do colibri) e `NOTICE` na raiz citando upstream original, fork vendorizado
  e commit exato. Headers de copyright existentes nos arquivos-fonte são
  preservados.
- Build: um alvo `add_custom_target` no CMake delega ao `engine/c/Makefile`
  existente. O Makefile não é reescrito em CMake puro — é a ferramenta de
  build nativa e testada do motor. `runtime/` e `apps/` (exceto o novo
  `apps/web-chat/`, que é código do colibri) permanecem intocados.
- Dono: us4-core. Migração incremental do runtime nativo para cobrir as
  mesmas capacidades é permitida a qualquer momento e **não exige novo ADR**
  até que o contrato público (`CLI-CONTRACT.md`, formatos de shard/cache)
  precise mudar por causa disso.

---

## Consequências

### Positivas (+)

- Caminho rápido para rodar modelos tier-1 MoE em hardware modesto, sem
  esperar a reimplementação completa em C++/MLX.
- Motor já testado (testes C e Python próprios) e com atribuição legal
  correta desde o primeiro commit.
- Runtime nativo continua evoluindo sem pressão de deadline artificial —
  a engine tier absorve a demanda imediata.

### Negativas (-)

- Duas stacks de inferência coexistem temporariamente (C puro em `engine/`
  e C++/MLX em `runtime/`), com duplicação de conceitos (tokenizer, KV
  cache, quantização) até que uma migração incremental unifique os dois ou
  se decida manter ambos por design.
- `engine/` roda no processo Python (doctor.py, openai_server.py,
  resource_plan.py) e no binário C, um modelo de execução diferente do
  runtime C++ nativo — exige atenção redobrada de quem contribui nos dois.
- Superfície de manutenção cresce: `engine/` precisa de sync periódico com
  o upstream do fork.

### Neutras / observações

- `engine/` não entra no `cmake --build build` default de produção do
  binário `us4-cli`; é um alvo adicional (`add_custom_target`), então não
  afeta o tempo de build nem os artefatos do runtime nativo.
- Este ADR não aprova GGUF, mudança funcional no motor, nem integração de
  CI para `engine/` — isso é escopo de issues subsequentes da épica #116.

---

## Alternativas consideradas

### Alternativa A — Reimplementação C++ imediata

- Resumo: portar as capacidades do colibri (MoE completo, streaming de
  disco, kernels quantizados) direto para `runtime/` em C++/MLX, sem passar
  por vendoring.
- Por que foi descartada: adiaria a entrega por múltiplos sprints e
  duplicaria trabalho de depuração já feito no colibri. O código C já
  funciona; reescrever antes de ter um baseline validado é risco
  desnecessário.

### Alternativa B — Git submodule apontando para o fork

- Resumo: referenciar `https://github.com/wesleysimplicio/colibri` como
  submodule em vez de copiar o código.
- Por que foi descartada: submodules exigem `git submodule update --init`
  extra em todo clone/CI, dificultam patches locais rápidos ao motor
  (necessários nas próximas issues da épica), e tornam o histórico do
  motor uma dependência externa fora do controle deste repositório. Vendoring
  com atribuição documentada dá controle total e histórico único, ao custo
  de sync manual — aceitável dado que o motor está congelado funcionalmente
  nesta issue.

---

## Critério de revisão

- Se o runtime nativo em `runtime/` atingir paridade funcional completa com
  `engine/` (MoE completo, streaming de disco, quantização int8/int4/int2,
  speculative decoding) e a decisão for descontinuar `engine/`, abrir novo
  ADR ("Supersedes ADR-010") documentando o desligamento.
- Se o contrato público do motor (formato de shard, CLI do `coli`, API do
  `openai_server.py`) precisar mudar para se integrar ao runtime nativo,
  revisitar este ADR.
- Revisar em até 2 sprints se o sync com o fork upstream ainda não tiver
  ocorrido nenhuma vez.

---

## Links

- Issue / task: #117 (épica #116)
- PR de implementação: (preenchido no PR)
- Documentos relacionados: [DESIGN](./DESIGN.md), [PATTERNS](./PATTERNS.md), [engine/README](../../engine/README.md)
- ADRs relacionados: [ADR-001](./ADR-001-mlx-primary-backend.md), [ADR-002](./ADR-002-runtime-boundaries-and-adapter-contract.md), [ADR-006](./ADR-006-moe-expert-paging.md)
- Referências externas: [colibri upstream](https://github.com/JustVugg/colibri), [colibri fork vendorizado](https://github.com/wesleysimplicio/colibri) (commit `8f5f3e3a2b7bef53daa1cc8608df6d91fc9a54eb`)
