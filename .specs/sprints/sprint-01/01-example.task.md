---
id: TASK-001
title: Implementar autenticação por email + senha
sprint: sprint-01
owner: @<TEAM>
status: doing
---

# TASK-001 — Implementar autenticação por email + senha

> Esta é uma task de exemplo para ilustrar como preencher o `task-template.md`. O tópico foi escolhido por ser neutro e comum na maioria dos produtos, mas o conteúdo deve ser tratado como ilustrativo. Em um projeto real, ajustar números, nomes de módulos e URLs de acordo com a stack `<STACK>` adotada.

## Contexto

O <PRODUCT_NAME> ainda não tem fluxo de identidade. Hoje qualquer pessoa que acessa a aplicação cai direto na home, o que impede:

- Personalizar a experiência por usuário em <DOMAIN>.
- Restringir áreas administrativas internas de `<TEAM>`.
- Cumprir a auditoria mínima exigida no roadmap (rastrear quem fez o quê).

A persona principal impactada é o `Operador de <DOMAIN>` (ver `.specs/product/PERSONAS.md`), que precisa de uma sessão estável para usar o produto durante turnos de trabalho. Origem: item #1 do `BACKLOG.md`. Esta task é o primeiro deliverable da sprint-01 e desbloqueia tasks de cadastro (#4) e recuperação de senha (#5).

## Acceptance Criteria

- [ ] AC-1 — Quando o usuário envia email válido + senha válida, o backend responde `200 OK` com cookie de sessão `httpOnly` e `secure` em ambientes não-locais.
- [ ] AC-2 — Quando email ou senha são inválidos, o backend responde `401` com mensagem genérica ("credenciais inválidas") sem revelar qual campo falhou.
- [ ] AC-3 — Após 5 tentativas inválidas em 10 minutos para o mesmo email, o backend retorna `429` por mais 15 minutos.
- [ ] AC-4 — A senha é armazenada com `bcrypt` (custo ≥ 12). Em hipótese alguma o texto puro chega ao banco ou aos logs.
- [ ] AC-5 — A interface de login renderiza corretamente em viewports de 375px e 1280px, com foco visível e mensagens de erro acessíveis (ARIA `aria-live="polite"`).
- [ ] AC-6 — Sessões expiram em 12 horas de inatividade e podem ser invalidadas manualmente via endpoint `POST /auth/logout`.
- [ ] AC-7 — A operação completa (login feliz) responde em até 400ms p95 sob carga de 50 RPS em staging.

## Out of scope

- Não inclui cadastro público de novos usuários (TASK-004).
- Não cobre fluxo de "esqueci minha senha" (TASK-005, depende de provedor de email).
- Não implementa MFA/2FA — fica para a sprint-03 após decisão em ADR.
- Não trata SSO (Google, Microsoft) — explicitamente fora desta sprint.
- Não inclui internacionalização das mensagens de erro: usar pt-BR fixo até a TASK-008.

## Test plan

### Unit

- [ ] Função `hashPassword` cobre custo válido, custo inválido, input vazio.
- [ ] Função `comparePassword` retorna `false` em hash corrompido sem lançar exceção que vaze stack trace.
- [ ] Validação de email rejeita formatos inválidos comuns (`a@b`, `@b.com`, `a@b.`, com espaço, com caractere unicode em domínio).
- [ ] Política de senha: mínimo 10 caracteres, ao menos 1 número, 1 letra maiúscula, 1 letra minúscula.
- [ ] Cobertura mínima de 85% nos arquivos `auth/*` novos.

### Integration

- [ ] `POST /auth/login` com payload válido cria registro em tabela `sessions` e retorna cookie.
- [ ] `POST /auth/login` com payload inválido não cria registro e mantém contador de tentativas atualizado.
- [ ] Rate limit por email persiste corretamente entre reinícios da aplicação (storage compartilhado).
- [ ] `POST /auth/logout` invalida a sessão e cookies subsequentes retornam `401`.
- [ ] Migração de banco roda sem erros em base limpa e em base com dados anteriores.

### End-to-end (Playwright)

- [ ] Cenário feliz: usuário válido faz login, é redirecionado para `/dashboard`, screenshot do dashboard salvo.
- [ ] Cenário de credencial inválida: mensagem genérica aparece, foco volta para o campo email, sem leak no DOM.
- [ ] Cenário de rate limit: após 5 tentativas erradas, mensagem específica aparece e botão fica desabilitado.
- [ ] Sessão expirada: simular cookie vencido, verificar redirect para `/login` preservando `?next=/dashboard`.
- [ ] Viewport mobile (375px) e desktop (1280px) com screenshot em ambos.
- [ ] Logout encerra sessão e botões protegidos somem da UI.

```bash
npm run lint
npm test -- --coverage
npm run test:e2e -- --project=chromium
npm run test:e2e -- --project=mobile-chrome
```

## Definition of Done

- [ ] Todos os ACs marcados.
- [ ] Suítes unit, integration e e2e verdes localmente e no CI.
- [ ] Cobertura de `auth/*` ≥ 85% conforme report do CI.
- [ ] PR aberto referenciando `BACKLOG.md#1`, `SPRINT.md` e ADR-001.
- [ ] Code review aprovado por 1 revisor de `<TEAM>` + 1 revisor de segurança.
- [ ] Documentação atualizada: README, `.specs/architecture/PATTERNS.md` (seção "Autenticação") e changelog.
- [ ] ADR-002 ("Estratégia de hashing e sessão") em estado `accepted`.
- [ ] Status atualizado em `BACKLOG.md` (item #1) e em `SPRINT.md` (deliverable 1).
- [ ] Evidências Playwright anexadas no PR (screenshots + traces dos cenários acima).

## Pegadinhas conhecidas

- **Cookie `secure`** quebra silenciosamente em `localhost` se HTTPS não estiver configurado. Usar flag condicional por ambiente.
- **Bcrypt custo 12** adiciona 200-400ms ao login em hardware modesto. Confirmar SLA do AC-7 com benchmark antes de merge.
- **Rate limit em memória** reseta a cada deploy. Usar storage compartilhado (Redis ou equivalente) desde o começo para evitar retrabalho.
- **Mensagem de erro em dois idiomas**: hoje só pt-BR, mas a estrutura precisa permitir trocar para outras línguas sem refator (pensar em chave + lookup, não string literal espalhada).
- **Logs**: cuidado com middleware que logga corpo de requisição completo. Adicionar redator que substitua o campo `password` por `[REDACTED]` antes de qualquer transporte.
- **Migrations destrutivas**: a tabela `sessions` ainda não existe; rodar `migrate up` em ambiente sujo pode falhar. Garantir idempotência.

## Links

- Backlog: `.specs/sprints/BACKLOG.md` (item #1)
- Sprint: `.specs/sprints/sprint-01/SPRINT.md` (deliverable 1)
- Vision: `.specs/product/VISION.md`
- Domain: `.specs/product/DOMAIN.md` (entidade `User`, `Session`)
- Personas: `.specs/product/PERSONAS.md` (Operador de <DOMAIN>)
- Arquitetura: `.specs/architecture/DESIGN.md` (módulo `auth`)
- Patterns: `.specs/architecture/PATTERNS.md` (seção "Autenticação")
- ADRs: `ADR-002-hashing-strategy.md` (a criar nesta sprint)
- Issue: `#1`
- PR: `#<numero>` (preencher ao abrir)
