# Pull Request

## Resumo

<!-- Descreva em 1-3 frases o que muda e por quê. Foco no "porquê", não no "como". -->

## Task relacionada

<!-- Link obrigatório para a task: #NNN, .specs/sprints/sprint-XX/NN-titulo.task.md, ou issue. -->

- Task: <!-- ex: #42 ou .specs/sprints/sprint-01/01-example.task.md -->
- Closes: <!-- Closes #42 -->

## Tipo de mudança

- [ ] feat — nova feature
- [ ] fix — bug fix
- [ ] refactor — refactor sem mudança comportamental
- [ ] perf — melhoria de performance
- [ ] docs — documentação
- [ ] test — só testes
- [ ] chore — build/CI/tooling
- [ ] breaking — quebra contrato (descrever em "Breaking changes")

## Definition of Done

- [ ] Acceptance criteria da task atendidos
- [ ] Lint passa local (`npm run lint`)
- [ ] Unit tests passam (`npm test`)
- [ ] Coverage >= 80%
- [ ] E2E Playwright passa (`npx playwright test`)
- [ ] Evidência E2E anexada (screenshots/trace) abaixo
- [ ] Sem TODO/FIXME novos sem issue tracked
- [ ] Sem secrets/credenciais hardcoded
- [ ] Conventional commits seguidos no histórico
- [ ] Documentação atualizada (`README.md`, `.specs/`, JSDoc) quando aplicável
- [ ] Changelog atualizado se mudança user-facing
- [ ] Versão bumped conforme SemVer (`package.json`)
- [ ] ADR linkado se mudou `architecture/` (ADR-NNN)

## Evidências / Screenshots

<!-- Anexe screenshots, gifs, traces do Playwright. Para cada cenário coberto, mostre estado final. -->
<!-- Exemplo: -->
<!-- ![happy-path](url) -->
<!-- ![error-state](url) -->

## Cenários E2E cobertos

- [ ] Caminho feliz
- [ ] Casos de erro (input inválido, falha de rede)
- [ ] Estados de auth (anônimo, logado, sem permissão)
- [ ] Variantes de viewport (mobile, desktop)
- [ ] Edge cases relevantes

## Breaking changes

<!-- Se aplicável, descreva impacto e migração. Caso contrário, "N/A". -->

## Notas de deploy

<!-- Variáveis de ambiente novas, migrations, side effects de deploy. "N/A" se nenhum. -->

## Checklist do reviewer

- [ ] Código segue `.specs/architecture/PATTERNS.md`
- [ ] Testes cobrem o comportamento, não apenas linhas
- [ ] Sem refatoração extra fora do escopo
- [ ] Mensagens de commit seguem Conventional Commits
