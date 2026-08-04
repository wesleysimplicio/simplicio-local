# BOOTSTRAP - Agentic Starter aplicado neste repositorio

Este documento registra como o Agentic Starter deve ser usado dentro do
`us4-v6-simplicio-apple`.

## Objetivo

Manter uma base agentica completa para o US4 V6 Apple Edition:

- instrucoes compartilhadas entre agentes (`AGENTS.md`, `CLAUDE.md`, Copilot);
- specs como codigo em `.specs/`;
- skills e custom agents versionados;
- gates de qualidade e Definition of Done;
- handoff claro para novas sessoes de Codex/Claude/Copilot/Cursor/Aider.

## Contrato da versao atual

O starter mais novo trabalha assim:

- detecta `PRODUCT_NAME` por manifestos, nao so pelo nome da pasta;
- detecta `project_mode` (`root` vs `monorepo`) via `projects/`;
- substitui apenas `<PRODUCT_NAME>` e `<STACK>` no bootstrap;
- infere `team`, `domain`, `vision` e `personas` lendo o codigo, sem
  perguntar ao humano por padrao;
- suporta handoff para `claude`, `codex`, `cursor`, `vscode`, `windsurf`,
  `kiro`, `copilot`, `aider`, `hermes` e `openclaw`.

## O que ja esta instalado

```text
.agents/
.claude/
.codex/
.github/
.skills/
.specs/
AGENTS.md
CLAUDE.md
INIT.md
README.md
README.pt-BR.md
playwright.config.ts
bootstrap.sh
bootstrap.ps1
bin/cli.js
test/
tests/
```

## Como validar o scaffold

```bash
npm run lint
npm test
npm run test:cli
npm run pack:dry
```

Esses checks cobrem o CLI e a estrutura do starter. Eles nao substituem os
checks do runtime C++:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
npx playwright test
```

## Regras de manutencao

- Atualize `AGENTS.md`, `CLAUDE.md` e `.github/copilot-instructions.md` juntos.
- Nao adicione dependencia nova sem confirmacao humana.
- Nao altere codigo de runtime durante manutencao do starter.
- Se um workflow de agente mudar, registre em `.specs/workflow/`.
- Se uma decisao arquitetural mudar, registre ADR.

## Proximo marco natural

Criar tasks concretas de sprint a partir de `.specs/sprints/sprint-01/SPRINT.md`
e iniciar `T01.1` com CMake/runtime skeleton, mantendo este bootstrap como
infra de trabalho.

<!-- simplicio-global-llm-architecture-rules:start -->
## Regras arquiteturais obrigatórias para qualquer LLM

Estas regras valem para análise, planejamento, implementação, revisão, testes,
release e documentação neste ecossistema. O agente deve lê-las antes de agir:

1. **Não mantenha compatibilidade retroativa.** O que está obsoleto deve ser
   deletado diretamente. Não adicione camadas de compatibilidade, migrações ou
   fallbacks.
2. **Escolha a implementação mais simples que atende à necessidade atual.**
   Não crie abstrações preventivas nem camadas de configuração desnecessárias.
3. **Divida o sistema em camadas longas.** Faça primeiro uma versão mínima
   end-to-end funcionando; depois adicione capacidades por cima. Não desmonte
   algo que funciona por complexidades inacabadas.
4. **Mantenha os componentes modulares**, com responsabilidades claramente
   separadas e limites explícitos.
5. **Priorize bibliotecas maduras e mantidas.** Não reescreva do zero sem
   motivo técnico explícito e registrado.
6. **Inspecione primeiro as dependências existentes.** Antes de adicionar um
   pacote ou escrever uma solução própria, verifique o que o projeto já possui.
7. **Decida a arquitetura pensando no longo prazo.** Não aceite soluções
   temporárias com a intenção de mudar depois.
8. **Use padrões de produtos maduros.** Pesquise como soluções consolidadas
   resolvem o mesmo problema e reutilize padrões validados; não reinvente a roda.

<!-- simplicio-global-llm-architecture-rules:end -->

