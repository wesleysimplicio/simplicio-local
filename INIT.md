# INIT - Agentic Starter no US4 V6 Apple Edition

> Este arquivo e o handoff operacional do Agentic Starter. Ele existe para
> agentes que entram no repositorio depois do bootstrap e precisam entender
> o que ja foi instalado, o que podem tocar e qual e a proxima acao segura.

## Estado atual

O starter ja foi aplicado neste repositorio e adaptado para o projeto
**US4 V6 Apple Edition**. A raiz contem:

- `AGENTS.md`, `CLAUDE.md` e `.github/copilot-instructions.md` alinhados.
- `.specs/` com produto, arquitetura, workflow, backlog e 12 sprints.
- `.agents/` e `.github/copilot/agents/` com agentes reutilizaveis.
- `.skills/` com skills locais.
- `.claude/` e `.codex/` com hooks/configuracao de agentes.
- `.github/workflows/` com gates de CI/DoD.

Nao rode um bootstrap generico por cima sem revisar o diff. Este repo ja tem
contexto especifico de runtime C++ para Apple Silicon.

O contrato mais novo do starter assume inferencia por leitura de codigo:

- `team`, `domain`, `vision` e `personas` devem ser inferidos do repo.
- `projects/` pode representar modo `monorepo`.
- `.starter-meta.json` e a fonte de verdade operacional para esse handoff.

## Regra zero

Preserve o trabalho existente. Antes de editar:

1. Leia `AGENTS.md`.
2. Leia a task em `.specs/sprints/sprint-XX/*.task.md`, quando existir.
3. Leia `.specs/architecture/PATTERNS.md` e ADRs relevantes.
4. Confira `git status --short`.

Se houver mudancas que voce nao fez, trabalhe com elas. Nao reverta sem pedido
explicito do humano.

## Escopo permitido para o starter

Arquivos gerenciados pelo starter:

```text
AGENTS.md
CLAUDE.md
README.md
README.pt-BR.md
playwright.config.ts
.agents/**
.claude/**
.codex/**
.github/copilot-instructions.md
.github/copilot/**
.github/ISSUE_TEMPLATE/**
.github/PULL_REQUEST_TEMPLATE.md
.github/workflows/**
.skills/**
.specs/**
```

Codigo de runtime (`runtime/**`, `CMakeLists.txt`, kernels Metal/MLX/NEON,
benchmarks e testes C++) pertence as tasks de sprint. Nao crie nem altere essa
superficie como parte do bootstrap, salvo quando a task pedir.

## Como continuar daqui

1. Para uma task tecnica, crie ou leia um arquivo
   `.specs/sprints/sprint-XX/<id>.task.md`.
2. Siga o loop do `AGENTS.md`: read, plan, edit, format/lint, unit, e2e,
   regression/correctness, fix, commit, PR.
3. Se a task tocar CLI/UX, rode Playwright com evidencia em `test-results/` e
   `playwright-report/`.
4. Se mudar contrato arquitetural, crie ADR em `.specs/architecture/`.

Se este repo voltar a usar o bootstrap em outro workspace, o agent nao deve
perguntar sobre produto, dominio ou personas antes de ler o codigo.

## Checklist de bootstrap

- [x] Instrucoes mestre em `AGENTS.md`.
- [x] Espelho Claude em `CLAUDE.md`.
- [x] Espelho Copilot em `.github/copilot-instructions.md`.
- [x] Specs de produto e backlog preenchidos para US4.
- [x] Workflows e templates de PR/issue presentes.
- [x] Skills e agents locais presentes.
- [x] Config Codex em `.codex/config.toml`.
- [x] Testes smoke do CLI do starter presentes em `test/`.

## Validacao rapida

```bash
npm run lint
npm test
npm run test:cli
npm run pack:dry
```

Os comandos acima validam a parte Node/scaffold. Para runtime C++, use os
comandos do `AGENTS.md` e da task de sprint correspondente.

<!-- simplicio-global-llm-architecture-rules:start -->
## Regras arquiteturais obrigatórias para qualquer LLM

Estas regras valem para análise, planejamento, implementação, revisão, testes,
release e documentação neste ecossistema. O agente deve lê-las antes de agir:

1. **Não mantenha compatibilidade retroativa.** O que está obsoleto deve ser
   deletado diretamente. Não adicione camadas de compatibilidade, migrações ou
   fallbacks para preservar comportamento antigo.
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

