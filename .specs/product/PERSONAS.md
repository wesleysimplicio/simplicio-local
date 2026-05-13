# Personas — US4 V6 Apple Edition

## P1 — ML Engineer (primary)
- Roda Llama / DeepSeek / Qwen / Mistral local em MacBook Pro M3/M4/M5.
- Quer benchmark consistente entre modelos sem trocar de tool.
- Precisa de KV cache eficiente pra prompts longos (RAG, code review).
- Dores: llama.cpp nao tem auto-tune; MLX-LM so suporta alguns modelos; Ollama esconde tuning.
- Ganha com US4: 1 binary, 9 adapters, auto-tune, hot-cold KV, JSON output programatico.

## P2 — Researcher
- Compara arquiteturas (dense vs MoE vs ternary) em mesma maquina, mesma quantizacao.
- Precisa de correctness diff vs reference HF.
- Quer telemetria detalhada (expert hit-rate, prefetch hit, KV tier breakdown).
- Dores: cada framework reporta metricas diferente; reproduzir bench leva dia.
- Ganha com US4: matriz unificada, correctness gates, telemetria padronizada.

## P3 — App Developer
- Constroi app local-first / privacy-first em macOS (Swift app embutindo runtime).
- Precisa de SDK estavel (`us4-v6.dylib`), latencia previsivel, footprint memoria limitado.
- Quer modos MICRO/MICRO_PLUS pra rodar em MacBook Air 16GB.
- Dores: nenhum runtime entrega bom UX em RAM limitado sem perder qualidade.
- Ganha com US4: modes ULTRA_LOW/MICRO/MICRO_PLUS, BitNet/Ternary adapters, KV summarization.

## P4 — Sysadmin / DevOps (secondary)
- Gerencia fleet de Macs corporativos rodando inferencia local (compliance, no cloud).
- Precisa de deploy via MDM, telemetria exportavel (Prometheus/OTLP), update path.
- Dores: instalar Python + deps + modelos quebra com macOS updates.
- Ganha com US4: binary universal assinado, telemetria estruturada, sem deps externas.
