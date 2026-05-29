# Serve OpenAI-Compatible - `us4-cli serve`

> Origem: Sprint roadmap (dense adapter Qwen via MLX) + integracao com clients
> OpenAI-shape (simplicio-cli, langchain, raw curl). Este documento eh
> normativo: testes Playwright e CI do DoD validam o contrato aqui.

## 1. Escopo

- Cobre o subcomando `us4-cli serve` e o sidecar Python
  `scripts/openai_serve.py`.
- Cobre os fluxos:
  - `POST /v1/chat/completions` (proxied)
  - `POST /v1/completions` (proxied)
  - `POST /v1/embeddings` (in-process)
  - `GET /v1/models`
  - `GET /health` (alias `GET /v1/health`)
- Nao cobre o runtime nativo (CLI `run`, `--probe`, fixtures). Esses ficam em
  `CLI-CONTRACT.md` e `HARDWARE-PROBE.md`.

## 2. Arquitetura

```
  ┌────────────────────────┐         ┌──────────────────────────────┐
  │  OpenAI-shape client   │         │  mlx_lm.server (subprocess)  │
  │  (simplicio-cli, etc.) │         │  http://127.0.0.1:PORT+1     │
  └───────────┬────────────┘         └───────────────▲──────────────┘
              │ HTTP                                  │ HTTP (reverse proxy)
              ▼                                       │
  ┌────────────────────────────────────────────────────┴──────────────┐
  │  scripts/openai_serve.py (stdlib http.server, ThreadingHTTPServer)│
  │  ──────────────────────────────────────────────────────────────── │
  │  GET  /health, /v1/health                                         │
  │  GET  /v1/models                                                  │
  │  POST /v1/chat/completions  -> _proxy_upstream  -> mlx_lm.server  │
  │  POST /v1/completions       -> _proxy_upstream  -> mlx_lm.server  │
  │  POST /v1/embeddings        -> _handle_embeddings  (mlx-embeddings│
  │                                                       in-process) │
  └───────────────────────────────────────────────────────────────────┘
                      ▲
                      │ execvp(python3, scripts/openai_serve.py)
              ┌───────┴────────┐
              │   us4-cli      │  (apps/cli/main.cpp)
              │   serve …      │
              └────────────────┘
```

- O CLI nativo (`us4-cli`) propaga flags via env vars `US4_SERVE_*` e troca
  o processo por `python3` com `execvp`. Apos `execvp`, o sidecar Python toma
  conta do TTY.
- Chat e proxied porque `mlx-lm >= 0.31` ja embarca um servidor
  OpenAI-compat completo. Reescrever isso em Python ou C++ violaria o
  principio "1 arquivo".
- Embeddings sao implementados localmente porque `mlx-embeddings` nao ship
  servidor.

## 3. CLI

### Sinopse

```
us4-cli serve [--host <addr>] [--port <n>]
              [--chat-backend <mlx|ollama|custom>]
              [--chat-upstream <url>]
              [--chat-model <id>] [--embed-model <id>]
              [--no-chat] [--no-embed]
```

### Flags

| Flag | Env var | Default | Descricao |
|---|---|---|---|
| `--host <addr>` | `US4_SERVE_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` para expor na LAN. |
| `--port <n>` | `US4_SERVE_PORT` | `8080` | Porta publica. O upstream `mlx_lm.server` sobe em `PORT+1`. |
| `--chat-backend <mlx\|ollama\|custom>` | `US4_SERVE_CHAT_BACKEND` | `mlx` | Seletor do upstream de chat. |
| `--chat-upstream <url>` | `US4_SERVE_CHAT_UPSTREAM` | unset | Override do upstream de chat, por exemplo `http://127.0.0.1:11434` para Ollama. |
| `--chat-model <id>` | `US4_SERVE_CHAT_MODEL` | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | Modelo de chat (Hugging Face id). |
| `--embed-model <id>` | `US4_SERVE_EMBED_MODEL` | `mlx-community/embeddinggemma-300m-bf16` | Modelo de embeddings. |
| `--no-chat` | `US4_SERVE_DISABLE_CHAT=1` | off | Desabilita chat (nao sobe `mlx_lm.server`). |
| `--no-embed` | `US4_SERVE_DISABLE_EMBED=1` | off | Desabilita embeddings (nao carrega `mlx-embeddings`). |
| (nao exposto via flag) | `US4_SERVE_SCRIPT` | `scripts/openai_serve.py` | Override do sidecar. Util para Homebrew tap. |
| (nao exposto via flag) | `US4_SERVE_PYTHON` | `python3` | Override do interpretador. |
| (nao exposto via flag) | `US4_SERVE_LOG_LEVEL` | `INFO` | Nivel de log do sidecar. |

### Exit codes

| Codigo | Significado |
|---|---|
| `0` | Shutdown gracioso (SIGINT/SIGTERM). |
| `1` | Falha na inicializacao (`execvp` falhou, script ausente, port em uso, etc.). |
| `2` | `mlx-lm` nao instalado e chat nao foi desabilitado. |
| `3` | `mlx-embeddings` nao instalado e embeddings nao foi desabilitado. |

## 4. HTTP Contract

### 4.1 `GET /health` (alias `GET /v1/health`)

Resposta `200 OK`:

```json
{
  "status": "ok",
  "chat": true,
  "embed": true
}
```

- `chat`, `embed`: booleans refletindo flags de enablement.
- Sempre retorna `200` quando o servidor esta no ar; nao indica saude do
  upstream `mlx_lm.server`. Para validar upstream, faca `POST` real.

### 4.2 `GET /v1/models`

Resposta `200 OK`:

```json
{
  "object": "list",
  "data": [
    {"id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", "object": "model", "created": 1716796800, "owned_by": "us4-local"},
    {"id": "mlx-community/embeddinggemma-300m-bf16",       "object": "model", "created": 1716796800, "owned_by": "us4-local"}
  ]
}
```

- `data` so contem entradas para os backends habilitados.
- `created` eh `time.time()` em segundos.
- `owned_by` eh sempre `"us4-local"`.

### 4.3 `POST /v1/chat/completions`

Proxied para `mlx_lm.server` no upstream port. O sidecar repassa request body,
status code, content-type e content-length. Streaming (`stream: true`) eh
suportado pelo proprio upstream.

Erros do sidecar (nao upstream):

| Status | Body |
|---|---|
| `503` | `{"error": {"message": "chat backend disabled (US4_SERVE_DISABLE_CHAT)", "type": "service_unavailable"}}` |
| `502` | `{"error": {"message": "chat upstream unreachable: <reason>", "type": "bad_gateway"}}` |

Erros do upstream sao propagados com status code e body do `mlx_lm.server`.

### 4.4 `POST /v1/completions`

Mesmo comportamento de `/v1/chat/completions` (proxied).

### 4.5 `POST /v1/embeddings`

Request body:

```json
{
  "model": "mlx-community/embeddinggemma-300m-bf16",
  "input": "hello world"
}
```

ou batch:

```json
{
  "model": "mlx-community/embeddinggemma-300m-bf16",
  "input": ["doc one", "doc two", "doc three"]
}
```

- `model` eh opcional. Se ausente, usa `US4_SERVE_EMBED_MODEL`.
- `input` eh **obrigatorio**. Aceita string ou lista de strings.

Resposta `200 OK`:

```json
{
  "object": "list",
  "data": [
    {"object": "embedding", "index": 0, "embedding": [0.012, -0.034]},
    {"object": "embedding", "index": 1, "embedding": [0.044, -0.012]}
  ],
  "model": "mlx-community/embeddinggemma-300m-bf16",
  "usage": {"prompt_tokens": 4, "total_tokens": 4}
}
```

- `usage.prompt_tokens` eh aproximacao baseada em `text.split()`. Eh tokenizer-
  agnostico de proposito (nao ha pretensao de matchar OpenAI byte-pair token
  count).

Erros:

| Status | Causa | Body |
|---|---|---|
| `400` | Body ausente ou nao-JSON | `{"error": {"message": "request body must be JSON with 'input' field"}}` |
| `400` | `input` ausente | `{"error": {"message": "missing 'input' field"}}` |
| `400` | `input` tipo invalido | `{"error": {"message": "'input' must be string or list of strings"}}` |
| `500` | Falha no `mlx-embeddings` | `{"error": {"message": "embedding failed: <detail>", "type": "internal_error"}}` |
| `503` | `--no-embed` ativo | `{"error": {"message": "embedding backend disabled (US4_SERVE_DISABLE_EMBED)"}}` |

### 4.6 Rotas desconhecidas

Qualquer outro path -> `404`:

```json
{"error": {"message": "not found: /<path>", "type": "not_found"}}
```

## 5. Integracao OpenAI client

Qualquer SDK OpenAI-shape funciona apontando para `http://127.0.0.1:8080/v1`.

### simplicio-cli

```bash
export SIMPLICIO_BASE_URL=http://127.0.0.1:8080/v1
export OPENAI_API_KEY=anything   # us4-cli serve nao valida o token
simplicio "explain this diff"
```

### Python (openai SDK)

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="anything")
client.chat.completions.create(
    model="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    messages=[{"role": "user", "content": "hi"}],
)
client.embeddings.create(
    model="mlx-community/embeddinggemma-300m-bf16",
    input="vector me",
)
```

### curl

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/v1/models
curl -s http://127.0.0.1:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input":"vector me"}'
```

## 6. Seguranca

- Bind default eh `127.0.0.1`. Mudanca para `0.0.0.0` eh decisao do operador.
- Nao ha autenticacao. O endpoint eh **local-only por design**. Para expor na
  rede, coloque atras de um reverse proxy autenticado (Caddy, nginx, Tailscale
  Funnel).
- O sidecar **nao loga request body**. Apenas method + path + status.
- Nenhum token, segredo, ou path-com-credencial deve ser passado via flag.
  Todos os secrets ficam em env. O CLI nao copia o ambiente do shell para um
  arquivo de configuracao.

## 7. Testes / DoD

Smoke obrigatorio no E2E (`tests/e2e/us4-cli-serve.spec.ts`):

- [ ] `serve --no-chat --no-embed --port <free>` sobe e responde
      `GET /health` com `{"status":"ok","chat":false,"embed":false}`.
- [ ] `GET /v1/models` retorna `data: []` com ambos backends desabilitados.
- [ ] `POST /v1/embeddings` retorna `503 service_unavailable` quando
      `--no-embed`.
- [ ] `POST /v1/chat/completions` retorna `503 service_unavailable` quando
      `--no-chat`.
- [ ] `GET /bogus` retorna `404 not_found`.
- [ ] Shutdown via SIGINT retorna exit code `0`.

Smoke completo (manual, fora de CI ate ter cache de modelo):

- [ ] `serve --no-embed` sobe e proxia `/v1/chat/completions` para
      `mlx_lm.server` com `model=Qwen2.5-Coder-7B-Instruct-4bit`.
- [ ] `serve --no-chat` carrega `embeddinggemma-300m-bf16` e responde
      `/v1/embeddings` com vetores de dimensao consistente.

## 8. Referencias cruzadas

- CLI: `apps/cli/main.cpp` (`RunServeCommand`)
- Sidecar: `scripts/openai_serve.py`
- Deps: `scripts/requirements-serve.txt`
- mlx-lm upstream: <https://github.com/ml-explore/mlx-examples/tree/main/llms/mlx_lm>
- mlx-embeddings upstream: <https://pypi.org/project/mlx-embeddings/>
- Contract base CLI: [`CLI-CONTRACT.md`](CLI-CONTRACT.md)
