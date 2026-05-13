# Vision — US4 V6 Apple Edition

## Problema
LLMs locais (DeepSeek/Kimi/MiniMax/GLM/Llama/Qwen/Gemma/BitNet) tem requisitos heterogeneos (dense, MoE, ternary) e ferramentas existentes (llama.cpp, MLX-LM, Ollama) servem **um modelo por vez**, sem unificacao de pipeline, sem auto-tuning hardware-aware, sem hot-cold KV tiering, sem speculative decoding multi-arquitetura. Em Apple Silicon (M1..M5+), recursos especificos (MLX, Metal, NEON, ANE) ficam subutilizados em runtimes generalistas.

## Quem usa
- Engenheiros ML rodando inferencia local em MacBook/Mac Studio.
- Pesquisadores comparando arquiteturas (dense vs MoE vs ternary) sem reescrever pipeline.
- Devs construindo apps com privacy-first / offline-first em Apple Silicon.
- Sysadmins entregando inferencia em fleet de Macs corporativos.

## Diferencial
- **1 runtime, 9 adapters** — DeepSeek MoE, Kimi MoE, MiniMax, GLM, Qwen, Llama, Gemma, BitNet, Ternary.
- **Hardware-aware auto-tuning** — descobre tile/batch optimal por chip+RAM no startup.
- **Hot-cold KV tiering** — unified memory hot, RAM warm, SSD cold, summarization fallback.
- **SP-MoE prefetch** — preve experts e carrega em paralelo, reduz latencia per-token >=20%.
- **Speculative decoding P-EAGLE/EAGLE-3** — >=1.8x speedup em dense + MoE.
- **ANE offload (M5+)** — dense layers vao pro Neural Engine, libera Metal pra hot path.
- **Single binary universal arm64** — sem Python, sem Docker, sem cluster.

## Metricas (post-v1.0)
- Latencia per-token vs llama.cpp em mesma quantizacao: >=1.5x mais rapido.
- Hit-rate hot KV: >=80% em prompts longos (8k+).
- Cobertura testes: >=80% touched files; correctness diff vs reference <= 1e-3 dense, <= 1e-2 BitNet.
- 7 RAM tiers (16/24/32/48/64/96/128 GB) suportados com mode auto.
- 9 adapters funcionando em pelo menos 1 chip M-series.

## Nao-objetivos
- Treinamento / fine-tuning (so inferencia).
- Cloud / distributed inference (single-machine focus).
- Suporte non-Apple (ver Windows Edition).
- GUI desktop app (CLI + biblioteca).

## Tese longo prazo
Inferencia LLM se torna commodity local-first. Quem controla o runtime universal (multi-adapter + multi-backend + auto-tune) reduz custo e democratiza modelos SOTA. US4 V6 e o pilar Apple desse runtime.
