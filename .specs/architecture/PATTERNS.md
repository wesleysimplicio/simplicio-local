# Patterns — `<PRODUCT_NAME>`

> Como escrever código aqui. Curto, opinativo, executável.
> Audiência: dev humano e agent AI. Se a regra não está aqui, vale o senso comum + revisão de PR.

---

## 1. Naming

| Item | Convenção | Exemplo bom | Exemplo ruim |
|------|-----------|-------------|--------------|
| Variáveis, funções, classes | inglês, descritivo | `userRepository`, `calculateInvoiceTotal` | `repoUsuario`, `calcTot` |
| Arquivos | kebab-case | `user-repository.ts`, `invoice-service.ts` | `UserRepository.TS`, `invoice_service.ts` |
| Pastas | kebab-case, plural quando coleção | `use-cases/`, `entities/` | `UseCase/`, `Entity/` |
| Componentes UI | PascalCase no símbolo, kebab-case no arquivo | `InvoiceCard` em `invoice-card.tsx` | `invoiceCard.tsx` |
| Branches | `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>` | `feat/login-with-email`, `fix/invoice-rounding` | `feature1`, `wesley-branch` |
| Commits | conventional commits | `feat: add login with email` | `update stuff` |
| Testes | mesmo nome do alvo + sufixo `.test` ou `.spec` | `user-service.test.ts` | `tests1.ts` |

Regra de ouro: nome conta o quê, não o como. `processData` é vago, `normalizeUserEmail` é claro.

---

## 2. Estrutura de pastas

Estrutura de referência (adaptar à `<STACK>`, manter os boundaries):

```
src/
  domain/
    entities/
    value-objects/
    services/            # serviços de domínio puros
  application/
    use-cases/
    dtos/
    ports/               # interfaces que o domínio precisa (repos, gateways)
  infrastructure/
    repositories/        # implementam ports
    adapters/            # clientes HTTP, SDK terceiros
    persistence/         # ORM, migrations
    logger/
  interface/
    http/
      routes/
      handlers/
      middlewares/
      validators/
    cli/
    workers/
  shared/
    errors/
    types/
    utils/
tests/
  unit/
  integration/
  e2e/
```

Regra: import nunca aponta de dentro pra fora. `domain/` não importa de `infrastructure/`.

---

## 3. Como criar endpoint novo

Passo a passo curto:

1. Adicionar rota em `src/interface/http/routes/<recurso>.ts`.
2. Criar handler em `src/interface/http/handlers/<recurso>-handler.ts`.
3. Criar (ou reusar) validator de input em `src/interface/http/validators/`.
4. Criar use case em `src/application/use-cases/<acao>-<recurso>.ts`. Retorno tipado.
5. Se precisa de IO novo: criar port em `src/application/ports/` e implementação em `src/infrastructure/`.
6. Escrever teste de integração (handler completo, banco de teste) ANTES da implementação subir.
7. Adicionar entrada na collection HTTP (Postman/Insomnia/REST Client) com exemplo request+response.
8. Atualizar OpenAPI/spec se existir.

Critério de feito: 200 happy path + 400 input inválido + 401/403 sem auth + 404 inexistente + 422 regra de negócio violada — todos cobertos por teste.

---

## 4. Como criar componente novo (UI)

1. Criar arquivo `src/components/<componente>/<componente>.tsx` (ou equivalente da `<STACK>`).
2. Props tipadas. Sem `any`. Defaults explícitos.
3. Sem fetch dentro do componente: dado vem por prop ou por hook custom (`useUserList()`).
4. Estilo no padrão da `<STACK>` (CSS modules, Tailwind, styled-components — escolher um e ficar).
5. Acessibilidade: roles, labels, foco visível, atalhos teclado.
6. Estados cobertos: loading, empty, error, success.
7. Storybook ou playground com cada estado.
8. Teste de componente (render + interação principal).
9. Teste e2e do fluxo onde o componente é usado.

Componente puro de apresentação não conhece API. Container resolve dado, presentational renderiza.

---

## 5. Como criar teste

Pirâmide: muitos unit, alguns integration, poucos e2e.

### Unit
- Cobre domínio e use case.
- Sem rede, sem disco, sem framework HTTP.
- Mocks só para ports (interfaces) — nunca para coisas internas do domínio.
- Tempo alvo: < 50ms por teste.

```typescript
// tests/unit/calculate-invoice-total.test.ts
test('aplica desconto quando cliente e VIP', () => {
  const invoice = makeInvoice({ items: [{ price: 100 }], customer: { tier: 'vip' } });
  expect(calculateInvoiceTotal(invoice)).toBe(90);
});
```

### Integration
- Cobre adaptadores (repo + banco real de teste, adapter + mock do terceiro).
- Banco em container, dados resetados entre testes.
- Tempo alvo: < 500ms por teste.

### E2E (Playwright)
- Cobre fluxos críticos do usuário ponta-a-ponta.
- Roda contra build de produção em ambiente isolado.
- Trace + screenshot + video on-failure (ver `playwright.config.ts`).
- Evidência (screenshot, trace.zip) anexada ao PR.

Regra: não comitar com teste vermelho. Não pular teste pra entregar mais rápido. Skip só com link pra issue de retomada.

---

## 6. Tratamento de erro

Princípio: validar na boundary, falhar rápido, propagar erro tipado.

- Edge: input inválido vira `400 Bad Request` antes de tocar domínio.
- Auth: token ausente ou inválido vira `401`. Token válido sem permissão vira `403`.
- Domínio: regra violada lança `DomainError` com código (`INVOICE_ALREADY_PAID`). Handler mapeia pra `422`.
- Infra: falha de IO lança `InfraError`. Handler logga e retorna `503` ou `500` conforme severidade.
- Inesperado: middleware global captura, gera `trace_id`, logga stack, retorna `500` genérico.

```typescript
// errors tipados, nao strings soltas
class DomainError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

if (invoice.isPaid()) {
  throw new DomainError('INVOICE_ALREADY_PAID', 'Invoice already paid');
}
```

Nunca `catch (e) { /* swallow */ }`. Se ignorar é decisão consciente, comentar por quê.

---

## 7. Logging

- Formato: JSON estruturado.
- Sempre incluir: `timestamp`, `level`, `trace_id`, `service`, `event`, `context`.
- Nunca logar: senha, token, CPF/SSN, número de cartão, endereço completo, body de pagamento, prompt com PII de usuário.
- Mascarar quando precisa contexto: `email: "u***@example.com"`.

| Nível | Quando usar |
|-------|-------------|
| `error` | Falha que afeta usuário ou requer ação humana |
| `warn` | Comportamento anormal mas recuperado (retry com sucesso, fallback) |
| `info` | Eventos de negócio relevantes (login, criação de pedido) |
| `debug` | Detalhe pra investigação. Desligado em prod. |

```typescript
logger.info('invoice.created', { invoice_id: id, customer_id: cid, total_cents: total });
```

Não logar request body inteiro — só o que importa pra debug.

---

## 8. Validação

- Validar uma vez na boundary. Domínio confia que input já é válido.
- Schema declarativo (zod, yup, joi, ajv, FluentValidation, conforme `<STACK>`).
- Mensagens de erro consistentes: `{ field, code, message }`.
- Validação de regra de negócio (saldo suficiente, prazo expirado) é domínio, não schema.

```typescript
// boundary
const schema = z.object({ email: z.string().email(), password: z.string().min(8) });
const input = schema.parse(req.body); // 400 se invalido

// dominio
if (account.balance < amount) throw new DomainError('INSUFFICIENT_FUNDS', '...');
```

Nunca validar a mesma coisa em 3 camadas. Duplicação de validação é dívida.

---

## 9. Imports

- Ordem: stdlib, libs externas, alias do projeto, relativo.
- Sem ciclos. CI deve quebrar em ciclo de import.
- Sem `import *`. Importar o que usa.

---

## 10. Quando dividir vs manter junto

- 3 ocorrências da mesma lógica = candidato a abstração. Antes disso, copiar é OK.
- Função maior que 50 linhas = considerar split.
- Arquivo maior que 300 linhas = quase certo split.
- Classe com mais de 7 métodos públicos = revisar responsabilidade.

Regra `<TEAM>`: simplicidade ganha de elegância. Código óbvio é melhor que código esperto.
