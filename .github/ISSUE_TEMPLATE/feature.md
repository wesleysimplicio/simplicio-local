---
name: Feature
about: Propor nova feature ou melhoria
title: "feat: "
labels: ["enhancement", "needs-triage"]
assignees: []
---

# Feature

## Contexto

<!-- Por que essa feature é necessária? Qual problema resolve? Quem é impactado? -->

## Persona

<!-- Quem usa? Link pra .specs/product/PERSONAS.md se aplicável. -->

## Proposta

<!-- Descrição da solução proposta em alto nível. -->

## Acceptance Criteria

<!-- Critérios testáveis em formato Given/When/Then ou checkboxes claros. -->

- [ ] Dado <contexto>, quando <ação>, então <resultado esperado>
- [ ] Dado <contexto>, quando <ação>, então <resultado esperado>
- [ ] ...

## Out of scope

<!-- O que NÃO faz parte dessa feature. Evita escopo virar bola de neve. -->

- ...

## Test plan

### Unit
- ...

### Integration
- ...

### E2E (Playwright)
- Cenário feliz: ...
- Cenários de erro: ...
- Estados de auth: ...
- Viewports: mobile (375px), tablet (768px), desktop (1280px)

## Definition of Done

- [ ] Acceptance criteria atendidos
- [ ] Coverage >= 80%
- [ ] E2E passa com evidência (screenshot/trace)
- [ ] Documentação atualizada (`.specs/`, README)
- [ ] ADR criada se decisão arquitetural relevante
- [ ] Lint, unit, e2e green em CI
- [ ] PR seguindo Conventional Commits

## Pegadinhas conhecidas

<!-- Edge cases, race conditions, dependências sutis. -->

## Links

- Task template: `.specs/sprints/task-template.md`
- Patterns: `.specs/architecture/PATTERNS.md`
- Workflow: `.specs/workflow/WORKFLOW.md`

## Dependências

<!-- Outras issues/PRs/serviços bloqueando ou bloqueados. -->

## Estimativa de complexidade

<!-- S / M / L / XL — baseado em incerteza, não em horas. -->
