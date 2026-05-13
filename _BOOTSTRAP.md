# 🚀 BOOTSTRAP — Agentic Starter Pack

**Para Claude Code executar com multi-agents.**

Wesley criou pasta vazia `/Users/wesleysimplicio/Projetos/novos/agentic-starter/`.
Sua missão: popular com starter completo + gerar apresentação PDF/PPT.

---

## 🎯 Mission

Criar template de repositório AI-friendly que Wesley possa `cp -R` em qualquer projeto novo. Tudo neutro/genérico (sem stack específica) com placeholders `<STACK>`, `<PRODUCT_NAME>`, etc.

Plus: apresentação visual sobre **"Como ser AI Agent Specialist"** baseada nos conceitos abaixo.

---

## 📁 File tree completo (criar TUDO)

```
agentic-starter/
├── README.md                          # explica o starter pack
├── AGENTS.md                          # instruction file Codex/Claude Code
├── CLAUDE.md                          # symlink ou cópia de AGENTS.md
├── .gitignore
│
├── .github/
│   ├── copilot-instructions.md        # instruction file Copilot
│   ├── copilot/
│   │   ├── tdd.agent.md               # custom agent: TDD specialist
│   │   ├── reviewer.agent.md          # custom agent: code review
│   │   └── architect.agent.md         # custom agent: arquitetura
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── feature.md
│   │   └── bug.md
│   └── workflows/
│       ├── ci.yml                     # lint + unit + e2e
│       └── dod.yml                    # gate Definition of Done
│
├── .specs/
│   ├── README.md                      # como navegar .specs
│   │
│   ├── product/
│   │   ├── VISION.md                  # 1 página, por que existe
│   │   ├── DOMAIN.md                  # entidades, glossário
│   │   └── PERSONAS.md                # quem usa
│   │
│   ├── architecture/
│   │   ├── DESIGN.md                  # diagrama Mermaid + boundaries
│   │   ├── PATTERNS.md                # como escrever código aqui
│   │   ├── ADR-template.md            # template ADR
│   │   └── ADR-001-example.md         # exemplo preenchido
│   │
│   ├── workflow/
│   │   ├── WORKFLOW.md                # branch, PR, deploy
│   │   ├── CONTRIBUTING.md            # como adicionar feature
│   │   └── RELEASE.md                 # processo de release
│   │
│   └── sprints/
│       ├── BACKLOG.md                 # tudo que falta
│       ├── task-template.md           # template task
│       └── sprint-01/
│           ├── SPRINT.md              # exemplo sprint
│           └── 01-example.task.md     # exemplo task preenchida
│
├── .skills/
│   ├── README.md                      # como criar/usar skills
│   ├── _template/
│   │   └── SKILL.md
│   ├── playwright-e2e/
│   │   └── SKILL.md                   # skill prontinha
│   └── conventional-commits/
│       └── SKILL.md                   # skill prontinha
│
├── .claude/
│   ├── settings.json
│   └── hooks/
│       ├── post-edit.sh               # lint+format auto pós-edit (bash)
│       ├── post-edit.ps1              # idem em PowerShell (Windows nativo)
│       ├── pre-commit.sh              # bloqueia commit vermelho (bash)
│       └── pre-commit.ps1             # idem em PowerShell (Windows nativo)
│
├── .codex/
│   └── config.toml                    # sandbox + approval + history
│
├── playwright.config.ts               # com trace/screenshot/video
│
└── presentation/
    ├── slides.md                      # source Marp
    ├── ai-agent-specialist.pdf        # output PDF
    └── ai-agent-specialist.pptx       # output PPTX
```

---

## 📝 Conteúdo de cada arquivo

### `README.md` (raiz)
Explicar: o que é o starter pack, como usar (`cp -R` em projeto novo), como customizar `<PLACEHOLDERS>`, ordem de leitura sugerida pra humano.

### `AGENTS.md` (raiz) — ⭐ ARQUIVO MAIS IMPORTANTE
Instruction file mestre. Sections:
- **Stack** (placeholder `<STACK>`)
- **Comandos importantes** (`npm run dev`, `npm test`, `npm run lint`)
- **Workflow loop OBRIGATÓRIO** (ler task → planejar → editar → lint → unit → e2e → fix loop → commit)
- **Definition of Done** com checklist
- **Padrões de código** (pointer pra `.specs/architecture/PATTERNS.md`)
- **Onde encontrar contexto** (`.specs/product/`, `.specs/architecture/`)
- **Proibido**: pular testes, mockar pra fazer passar, commit com vermelho, ignorar ADR
- **Skills disponíveis**: lista skills em `.skills/`
- **Comandos especiais**: como criar nova ADR, como abrir PR

### `CLAUDE.md`
Cópia de AGENTS.md ou nota explicando "ler AGENTS.md".

### `.github/copilot-instructions.md`
Espelho do AGENTS.md adaptado pra Copilot (mesmo conteúdo, ajusta tom). Foco em Agent Mode workflow.

### `.agents/ralph-loop.agent.md`
Custom agent **executor autônomo padrão** (Ralph Loop). Roda `read → plan → execute → lint → unit → e2e (Playwright com evidência) → fix → repeat` até DoD verde. Frontmatter:
```
---
name: Ralph Loop
description: Executor autônomo em loop contínuo até DoD verde, com Playwright + evidência obrigatória em toda task.
tools: [edit, terminal, search]
---
```

### `.agents/tdd.agent.md`
Custom agent TDD-first com frontmatter:
```
---
name: TDD Specialist
description: Escreve teste falhando antes do código. Loop red-green-refactor.
tools: [edit, terminal, search]
---
```

### `.agents/reviewer.agent.md`
Custom agent code review (sem editar, só comenta).

### `.agents/architect.agent.md`
Custom agent que só desenha arquitetura e cria ADRs, não escreve código de produção.

> Espelho em `.github/copilot/agents/<nome>.agent.md` para o GitHub Copilot Workspace. `.agents/` é canônico (padrão AGENTS.md ecosystem); o mirror em `.github/copilot/agents/` é para Copilot Coding Agent que lê estritamente desse caminho.

### `.github/workflows/ci.yml`
GitHub Actions: matrix de Node versions, npm install, lint, test --coverage, playwright install + test, upload artifacts (playwright-report, coverage).

### `.github/workflows/dod.yml`
Gate de PR: roda DoD checklist do AGENTS.md. Falha se coverage < 80%, se Playwright tem evidence faltando, se commit não é convencional.

### `.github/PULL_REQUEST_TEMPLATE.md`
Checklist DoD + link pra task.md + screenshots/evidências.

### `.github/ISSUE_TEMPLATE/feature.md`
Template feature seguindo formato task.md.

### `.github/ISSUE_TEMPLATE/bug.md`
Template bug com reprodução, ambiente, evidência.

### `.specs/README.md`
Mapa: por onde navegar. Ordem: VISION → DOMAIN → DESIGN → ADRs → SPRINT atual → tasks.

### `.specs/product/VISION.md`
1 página template:
- Problema que resolve
- Quem usa (link PERSONAS)
- Diferencial
- Métricas de sucesso
- Não-objetivos

### `.specs/product/DOMAIN.md`
Glossário + entidades de negócio. Tabela de termos. Diagrama de entidades simples em Mermaid.

### `.specs/product/PERSONAS.md`
2-3 personas com objetivos, frustrações, contexto de uso.

### `.specs/architecture/DESIGN.md`
Visão geral. Mermaid graph LR ou C4. Boundaries explicadas. Stack overview. Decisões principais (links pra ADRs).

### `.specs/architecture/PATTERNS.md`
- Naming (variáveis, files, branches)
- Estrutura de pastas
- Como criar endpoint novo
- Como criar componente novo
- Como criar teste
- Tratamento de erro
- Logging
- Validação

### `.specs/architecture/ADR-template.md`
Template ADR: Status, Contexto, Decisão, Consequências (+ e -), Alternativas consideradas.

### `.specs/architecture/ADR-001-example.md`
Exemplo preenchido fictício (ex: "ADR-001: Usar TypeScript em vez de JavaScript").

### `.specs/workflow/WORKFLOW.md`
- Branch strategy (trunk-based / git-flow)
- PR rules
- Code review protocol
- Deploy pipeline
- Hotfix process

### `.specs/workflow/CONTRIBUTING.md`
Step-by-step pra adicionar feature: criar task.md → branch → implementa → PR → review → merge.

### `.specs/workflow/RELEASE.md`
Como fazer release: changelog, version bump (semver), tag, deploy, rollback.

### `.specs/sprints/BACKLOG.md`
Lista priorizada. Formato: tabela com [#, título, prioridade, sprint alvo, status].

### `.specs/sprints/task-template.md`
Template completo:
- Contexto
- Acceptance Criteria (testáveis, checkboxes)
- Out of scope
- Test plan (unit + integration + e2e)
- Definition of Done
- Pegadinhas conhecidas
- Links

### `.specs/sprints/sprint-01/SPRINT.md`
Exemplo: objetivo, deliverables, riscos, dependências, dates.

### `.specs/sprints/sprint-01/01-example.task.md`
Exemplo task fictícia preenchida (ex: "Auth login com email+senha").

### `.skills/README.md`
Explicação skills: o que são, quando criar, como triggar (explicit `$skill` ou implicit via description), boas práticas.

### `.skills/_template/SKILL.md`
Template com frontmatter (name, description) + sections (Trigger, Steps, Padrões, DoD).

### `.skills/playwright-e2e/SKILL.md`
Skill pronta: como escrever teste Playwright nesse projeto (config, fixtures, page objects, evidências).

### `.skills/conventional-commits/SKILL.md`
Skill pronta: regras de commit (`feat:`, `fix:`, `chore:`, etc), exemplos, breaking changes.

### `.claude/settings.json`
Config Claude Code: cleanupPeriodDays alto, hooks habilitados, permissions sensatas.

### `.claude/hooks/post-edit.sh` + `.claude/hooks/post-edit.ps1`
Bash + PowerShell sibling. Rodam prettier+eslint --fix em files .ts/.tsx/.js/.jsx editados. Mesma lógica, melhor disponibilidade cross-platform (macOS/Linux/Git Bash usam .sh; Windows nativo PowerShell usa .ps1).

### `.claude/hooks/pre-commit.sh` + `.claude/hooks/pre-commit.ps1`
Bash + PowerShell sibling. Rodam `npm test --silent`, bloqueiam commit se vermelho.

### `.codex/config.toml`
Sandbox workspace-write, approval on-request, history ilimitado, model gpt-5.3-codex (placeholder).

### `playwright.config.ts`
Config completa com trace='on', screenshot on-failure, video on-failure, reporter html+json+junit, outputDir test-results.

### `.gitignore`
Padrão Node/TS + .env + test-results/ + playwright-report/ + coverage/ + .DS_Store + .codex local + .claude/sessions cache.

---

## 🎤 `presentation/` — Apresentação visual

**Tópico:** "Como virar AI Agent Specialist e entregar releases por dia"

**Stack sugerida:** Marp (markdown → PDF + PPTX, simples).

```bash
npm i -g @marp-team/marp-cli
marp slides.md --pdf -o ai-agent-specialist.pdf
marp slides.md --pptx -o ai-agent-specialist.pptx
```

**Estrutura de slides** (16-22 slides):

1. **Capa** — "AI Agent Specialist — Releases Diárias com Agents"
2. **O problema** — Dev solo lento, projetos morrem antes de terminar
3. **A virada** — Agents + estrutura = velocidade Anthropic-tier
4. **Mental model** — Tu = arquiteto/PM. Agent = executor. Spec = contrato.
5. **O loop universal** — diagrama (ler → planejar → editar → testar → corrigir → próximo)
6. **Stack de instruction files** — AGENTS.md, CLAUDE.md, copilot-instructions.md
7. **Anatomia do AGENTS.md** — sections obrigatórias
8. **Specs como código** — VISION, DOMAIN, DESIGN, ADRs
9. **ADRs — memória de longo prazo** — exemplo + por que importa
10. **Tasks atômicas** — task-template breakdown
11. **DoD com gate automático** — CI yml diagram
12. **Skills — capacidades reutilizáveis** — exemplo SKILL.md
13. **Hooks — automação no ciclo** — post-edit, pre-commit
14. **Custom agents** — TDD agent, reviewer agent
15. **Worktrees paralelos** — 3-5 agents simultâneos
16. **Playwright + evidências** — config + flow
17. **Fluxo diário** — manhã/tarde/noite breakdown
18. **Métricas que importam** — cycle time, PR size, reverts
19. **Hábitos de elite** — top 10
20. **Roadmap pra Specialist** — semana 1-2, mês 2, mês 3
21. **Pitfalls comuns** — drift composto, falsos verdes, context drift
22. **Próximo passo** — clonar starter, primeiro projeto

**Design:** tema dark profissional (Marp `gaia` ou custom). Diagramas Mermaid embedados quando fizer sentido. Bullets curtos. Code blocks com sintaxe colorida.

---

## 🤖 Squad de execução (multi-agents)

Aloca @gerente (Opus) como orchestrator. Spawn em paralelo onde não tem dependência:

| Agent | Responsabilidade | Files |
|-------|------------------|-------|
| **@docs-writer** | Produto/humano | README.md, .specs/product/* |
| **@architect** | Arquitetura/decisões | DESIGN.md, PATTERNS.md, ADR-template.md, ADR-001-example.md |
| **@workflow-writer** | Processo | WORKFLOW.md, CONTRIBUTING.md, RELEASE.md |
| **@sprints-writer** | Tasks/sprints | BACKLOG.md, task-template.md, sprint-01/* |
| **@skills-author** | Skills | .skills/README.md + 3 SKILL.md |
| **@config-writer** | AI configs | AGENTS.md, CLAUDE.md, copilot-instructions.md, copilot/*.agent.md, .claude/*, .codex/* |
| **@ci-engineer** | CI/CD/test | .github/workflows/*, playwright.config.ts, hooks .sh, PR/issue templates |
| **@presentation-designer** | Slides | presentation/slides.md + export pdf+pptx |

**Ordem:**
1. Paralelo: docs-writer, architect, workflow-writer, sprints-writer, skills-author, ci-engineer
2. Depois (depende dos acima): config-writer (AGENTS.md referencia tudo)
3. Depois: presentation-designer (consolida em slides)

**@gerente** valida cada handoff: arquivo existe? conteúdo bate com o brief? placeholders consistentes? Se não → reenfila pro agent.

---

## ✅ Definition of Done desse bootstrap

- [ ] Todos files do tree existem
- [ ] Nenhum file vazio (mínimo 30 linhas significativas)
- [ ] Placeholders consistentes: `<PRODUCT_NAME>`, `<STACK>`, `<TEAM>`, `<DOMAIN>`
- [ ] Mermaid diagrams renderizam (testar com `npx @mermaid-js/mermaid-cli` ou preview VS Code)
- [ ] Hooks `.sh` têm `chmod +x`
- [ ] `.gitignore` inclui artifacts certos
- [ ] PDF e PPTX gerados em `presentation/`
- [ ] PDF abre, slides legíveis
- [ ] Wesley consegue `cp -R agentic-starter/ ../novo-projeto/` e ter base AI-friendly
- [ ] README explica próximos passos pós-clone

---

## 🎬 Comando inicial pro Claude Code

Wesley vai abrir Claude Code dentro de `/Users/wesleysimplicio/Projetos/novos/agentic-starter/` e rodar:

```
Lê _BOOTSTRAP.md e executa. Use multi-agents (@gerente orquestra, spawn 
@docs-writer, @architect, @workflow-writer, @sprints-writer, @skills-author, 
@config-writer, @ci-engineer, @presentation-designer em paralelo onde possível).

Stack neutra com placeholders <STACK>/<PRODUCT_NAME>/<TEAM>/<DOMAIN>.

Apresentação Marp em presentation/, gera PDF + PPTX (instala marp-cli se 
precisar: npm i -g @marp-team/marp-cli).

Quando terminar, roda check final:
- find . -type f | wc -l (deve ser 35+)
- ls presentation/*.pdf presentation/*.pptx
- cat AGENTS.md | wc -l (deve ser 80+)

Reporta DoD do _BOOTSTRAP.md no fim.
```

---

## 💡 Notas de qualidade

- Todo `.md` deve ter cabeçalho com `# Título` claro
- Code blocks com linguagem (`bash`, `typescript`, `yaml`, `mermaid`)
- Bullets curtos (1-2 linhas)
- Exemplos concretos, não vago
- Caveman tone OK em comments, mas docs públicos (README) podem ser polidos
- Português pt-BR (Wesley é brasileiro)
- Nada de emoji no código fonte; pode usar em README/slides

---

**FIM DO BOOTSTRAP. Boa execução, time. 🚀**
