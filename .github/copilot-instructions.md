# Copilot Instructions

> Instruction file lido automaticamente pelo **GitHub Copilot Chat** e **Copilot Workspace / Agent Mode**. Espelha [AGENTS.md](../AGENTS.md) com foco em **Agent Mode workflow**.
>
> Ao trabalhar em Agent Mode, o Copilot pode delegar pra custom agents em [`.agents/`](../.agents/) (canônico, padrão AGENTS.md ecosystem) e/ou em `.github/copilot/agents/` (mirror lido pelo Copilot Coding Agent). Lista atual: `tdd.agent.md`, `reviewer.agent.md`, `architect.agent.md`.

---

## Stack

`<STACK>` (placeholder — substitui pela stack real do projeto, ex: `Node.js 20 + TypeScript + Next.js 14 + Playwright + Vitest`).

- Linguagem principal: `<STACK>`
- Framework web/API: `<STACK>`
- Banco de dados: `<STACK>`
- Test runner unit: `<STACK>` (Vitest, Jest, pytest, xUnit)
- Test runner E2E: **Playwright** (config em `playwright.config.ts`)
- Linter/formatter: `<STACK>` (ESLint + Prettier, Ruff, dotnet format)
- CI/CD: GitHub Actions (`.github/workflows/`)
- Deploy: `<STACK>` (ver `.specs/workflow/RELEASE.md`)

> Antes de adicionar dependência nova: pergunta ao humano. Sem exceção.

---

## Comandos importantes

```bash
# desenvolvimento
npm run dev
npm run build

# qualidade
npm run lint
npm run lint:fix
npm test
npm test -- --coverage

# E2E
npx playwright install
npx playwright test
npx playwright show-report

# git/PR
git checkout -b feat/<task-id>-<slug>
gh pr create --fill
gh run watch
```

Adapta pra `pnpm`, `yarn`, `bun`, `dotnet`, `python`, `go` conforme stack real.

---

## Workflow loop OBRIGATÓRIO (Agent Mode)

Em Copilot Workspace/Agent Mode, todo plano de execução segue esse loop. Não pula etapa.

1. **Ler task** — abre `.specs/sprints/sprint-XX/<task-id>.task.md`. Lê contexto + acceptance criteria + test plan + DoD.
2. **Plano explícito** — Copilot Workspace gera spec/plan. Revisa antes de implementar.
3. **Carregar contexto** — `.specs/architecture/PATTERNS.md` + ADRs relevantes em `.specs/architecture/ADR-*.md`. Skills aplicáveis em `.skills/`.
4. **Implementar (Agent Mode)** — edits cirúrgicos. Só toca o que a task pede. Sem refactor extra.
5. **Lint** — `npm run lint`. Vermelho = corrige.
6. **Unit** — `npm test`. Vermelho = corrige. Coverage do diff >= 80%.
7. **E2E (OBRIGATÓRIO em TODA task)** — `npx playwright test --reporter=list,html`. Captura **trace + screenshot + video** (todos). Sem evidência em `playwright-report/` + `test-results/` = task não fechada.
8. **Fix loop** — falhou? Volta ao 4. Repete até verde.
9. **Commit** — Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`). Mensagem em **inglês**.
10. **PR** — `gh pr create --fill`. Preenche template inteiro.

---

## Definition of Done

PR só faz merge quando todos os itens abaixo estão marcados:

- [ ] Unit tests passam
- [ ] Lint passa
- [ ] E2E Playwright passa **com evidência anexada em TODA task** — `playwright-report/index.html` + `test-results/<spec>/trace.zip` + screenshots por cenário + video. Hard rule: sem evidência, sem merge.
- [ ] Coverage do diff >= 80%
- [ ] Acceptance Criteria todos marcados
- [ ] PR template preenchido (link task + descrição + evidências)
- [ ] Conventional commit no merge
- [ ] ADR criado se mudou decisão arquitetural
- [ ] Changelog atualizado se release-relevant
- [ ] Sem warning novo, sem `console.log`/`print` deixado pra trás
- [ ] Sem TODO sem dono e sem prazo

CI bloqueia merge se DoD falhar (`.github/workflows/dod.yml`).

---

## Padrões de código

`.specs/architecture/PATTERNS.md` é a **fonte única**. Naming, estrutura, criação de endpoint/componente/teste, tratamento de erro, logging, validação — tudo lá.

Decisões irreversíveis viram **ADR** em `.specs/architecture/ADR-XXX-*.md` (template em `.specs/architecture/ADR-template.md`).

---

## Onde encontrar contexto

| Pergunta | Onde olha |
|---|---|
| Por que esse produto existe? | `.specs/product/VISION.md` |
| Quem é o usuário? | `.specs/product/PERSONAS.md` |
| Quais entidades de negócio? | `.specs/product/DOMAIN.md` |
| Como o sistema é desenhado? | `.specs/architecture/DESIGN.md` |
| Como escrever código aqui? | `.specs/architecture/PATTERNS.md` |
| Por que decidimos X? | `.specs/architecture/ADR-*.md` |
| Como faço PR/branch/release? | `.specs/workflow/WORKFLOW.md`, `RELEASE.md`, `CONTRIBUTING.md` |
| Backlog? | `.specs/sprints/BACKLOG.md` |
| Sprint atual? | `.specs/sprints/sprint-XX/SPRINT.md` |
| Skills? | `.skills/README.md` + `.skills/*/SKILL.md` |

---

## Proibido

- **Pular testes** — sem unit/E2E = sem merge.
- **Mockar pra fazer passar** — mock só pra dep externa real (HTTP, DB), nunca pra esconder falha.
- **Commit com vermelho** — lint/test falhando = não commita.
- **Ignorar ADR** — decisão registrada é lei.
- **Adicionar dependência sem perguntar.**
- **Editar arquivo não lido.**
- **Refactor escondido em PR de feature** — PR separado.
- **Force push em `main`/`master`.**
- **Commitar segredo** (`.env`, token, key, senha).
- **Reformatar arquivo inteiro num PR pequeno.**

---

## Custom agents (Copilot Workspace / Agent Mode)

Copilot pode delegar pra um custom agent quando a tarefa casa com a `description` do agent. Definidos em [`.agents/`](../.agents/) (canônico) e espelhados em `.github/copilot/agents/` (mirror para Copilot Coding Agent):

- **`ralph-loop.agent.md`** — Ralph Loop (padrão autônomo, Ralph Wiggum technique). Loop `read → plan → execute → lint → unit → Playwright → fix → repeat` até DoD verde. **No Copilot CLI**: `copilot --autopilot --yolo --max-autopilot-continues 20 -p "<prompt>"`. **No VS Code Agent Mode**: dropdown Mode → Agent + permission level **Autopilot** = continuous iteration nativo. Em outras ferramentas: Claude Code `/ralph-loop` (plugin oficial), Codex CLI `/goal`, Cursor Background Agent. Tools: `edit`, `terminal`, `search`.
- **`tdd.agent.md`** — TDD Specialist. Escreve teste falhando antes do código. Loop red-green-refactor. Tools: `edit`, `terminal`, `search`. Aciona quando tarefa exige cobertura nova ou regression test.
- **`reviewer.agent.md`** — Code Reviewer. Read-only. Comenta problemas e sugestões em PR. Tools: `search`, `read`. Aciona em revisão de PR aberto, sem editar arquivos.
- **`architect.agent.md`** — Architect. Desenha arquitetura, cria ADRs, atualiza `PATTERNS.md`. **Não escreve código de produção.** Tools: `edit`, `search`, `read`. Aciona em decisão arquitetural, refactor amplo, integração nova.

Pra invocar explicitamente em Copilot Chat: `@ralph-loop`, `@tdd`, `@reviewer`, `@architect`.

---

## Skills disponíveis (`.skills/`)

- **`playwright-e2e`** — como escrever teste Playwright. Trigger: nova feature de UI / fluxo end-to-end.
- **`conventional-commits`** — regras de commit (`feat:`, `fix:`, etc.). Trigger: hora de commitar.
- **`_template`** — base pra criar skill nova.

Detalhes em `.skills/README.md`.

---

## Comandos especiais

### Criar nova ADR

```bash
cp .specs/architecture/ADR-template.md .specs/architecture/ADR-XXX-<slug>.md
# preenche e commita junto com a feature
```

### Abrir PR

```bash
git push -u origin $(git branch --show-current)
gh pr create --fill
```

### Criar task

```bash
cp .specs/sprints/task-template.md .specs/sprints/sprint-XX/<id>-<slug>.task.md
```

### DoD local antes de push

```bash
npm run lint && npm test -- --coverage && npx playwright test
```

---

## Notas finais

- **Idioma**: docs em pt-BR, código em inglês, commits em inglês.
- **Sem emoji em código fonte.** README/slides ok.
- **Sem resumo no final** de resposta.
- **Sem estimativa de tempo.**
- **Pergunta apenas em ambiguidade real.**
- **Paralelismo** — research + read + review independentes rodam simultâneos em Agent Mode.
