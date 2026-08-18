# Damas local-first

Página standalone para jogar damas contra o Qwen3.8 27B pelo `llama-server`
OpenAI-compatible com TurboQuant. As regras e a validação de jogadas rodam no
navegador; o modelo só escolhe a jogada das pretas.

## Executar

```bash
python3 -m http.server 4173 --directory apps/checkers
```

Depois abra `http://127.0.0.1:4173/`. O endpoint padrão é
`http://127.0.0.1:18181/v1/chat/completions`; ele pode ser alterado na tela.

O servidor precisa anunciar `turbo3` e ser iniciado com flags equivalentes a:

```bash
llama-server --model Qwen3.8-27B-Q4_K_M.gguf \
  --cache-type-k turbo3 --cache-type-v turbo3 \
  --flash-attn auto --kv-unified --reasoning off
```

O benchmark reproduzível que mede as chamadas reais ao modelo está em
`scripts/benchmark-checkers.mjs` e gera o relatório em
`docs/benchmarks/checkers-qwen38-turboquant-2026-08-18.md`.
