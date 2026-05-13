# US4 V6 — Universal State Runtime

**Development Prompt — US4-V6-Simplicio**  
**Versão Refinada v3 — Maio 2026**

---

## Project Name & Positioning

**US4 V6** é a evolução **definitiva** do DS4/DS4++/DS4-v3/US4-V5.

- **DS4** = máxima especialização em **um único modelo**.
- **US4 V6** = **universal core + adapters especializados** + **tecnologias de 2026**:
  - MLX backend nativo
  - speculative expert prefetch
  - continuous batching
  - ternary PT-BitNet
  - hot-cold KV memory
  - Metal + MLX + NEON + ANE
  - auto-tuning por perfil real de MacBook

**Não é um runner genérico.**  
É **especialização por arquitetura + hardware-aware 2026** para Apple Silicon.

**Tagline oficial:**

> **US4 V6: Universal core, specialized adapters + 2026 SOTA, local LLMs optimized for real MacBooks.**

---

## Core Objective — V6

Criar um runtime universal que rode múltiplas famílias de modelos com performance **próxima ou superior ao nativo**, através de:

```text
Universal Core
+ Specialized Model Adapters
+ MLX/Metal/NEON/ANE backend selection
+ Memory virtualization
+ Adapter-specific quantization
+ Hardware-aware auto-tuning
```

O runtime deve otimizar:

- active RAM usage
- startup time
- time-to-first-token
- repeated prefill
- prefix cache reuse
- KV cache reuse
- SSD cold storage
- hot-cold dual-layer KV memory
- model-specific expert paging
- speculative expert prefetch
- Metal + MLX + ARM NEON + ANE hot paths
- continuous batching multi-session
- auto-tuning por perfil de MacBook
- correctness validation
- benchmark-driven optimization

---

## Important Rule

All performance numbers below are **targets to validate**, not guaranteed benchmark claims.

Do not hardcode benchmark wins.  
Do not claim final superiority without:

```text
real benchmark
hardware profile
model profile
correctness validation
before/after metrics
```

---

## New 2026 State-of-the-Art Technologies — V6

| Tecnologia | Descrição | Ganho esperado em Apple Silicon | Adapters impactados |
|---|---|---:|---|
| **MLX Backend Nativo** | Zero-copy unified memory, lazy evaluation, fusion ops | +30%–80% throughput target | Todos |
| **Speculative Expert Prefetching — SP-MoE / MoE-SpeQ** | Previsão de experts via hidden states + lightweight predictor | +1.8×–5.9× em MoE low-RAM target | DeepSeek, Kimi, MiniMax |
| **Ternary 1.58-bit + PT-BitNet** | Post-training ternary para modelos existentes | -50%–70% RAM target + até 4× velocidade target | BitNet + ternary adapter |
| **Continuous Batching + Hot-Cold Dual-Layer KV** | Múltiplas sessões + KV quente na RAM / frio no SSD | +3×–4× multi-session target | Todos |
| **P-EAGLE / EAGLE-3 Parallel Speculative Decoding** | Draft paralelo + tree speculation | +1.5×–2.5× tokens/s target | Todos, opcional por adapter |
| **Sparsity-Aware Expert Cache — MoE-Infinity style** | Cache que aprende padrões de ativação por sessão | 2.7×–13.7× latency improvement target em MoE | MoE adapters |
| **Neural Engine / ANE Offload — M5+** | Offload de ops leves: embedding, softmax, ranking, lightweight predictors | +15%–40% low-power target | Todos, auto-detect |
| **Content/Prefix-Aware Multimodal Cache** | Hashing de imagens/vídeos para multimodal context reuse | até 28× target em multimodal repeated context | Kimi, MiniMax |

---

## Target Hardware — MacBook 2026

| RAM | US4 V6 Mode | Foco principal |
|---:|---|---|
| **128 GB** | Full | Frontier MoE + long context + multi-session |
| **96 GB** | Balanced+ | Melhor target universal |
| **64 GB** | Degraded | Best cost/capability balance |
| **48 GB** | Ultra-Low | Mid-size models práticos |
| **32 GB** | Micro | Small dense + BitNet |
| **24 GB** | Micro+ | 1B–4B models + BitNet |
| **16 GB** | Nano | 1B–3B models + BitNet |

---

## Supported Model Families & Adapters — V6

| Adapter | Target Models | Architecture Focus |
|---|---|---|
| `us4_adapter_deepseek_moe` | DeepSeek V4 Flash, DeepSeek V3.x MoE | MoE, MLA, expert paging |
| `us4_adapter_kimi_moe` | Kimi K2.6, Kimi K2.5 | MLA + MoE, multimodal cache |
| `us4_adapter_minimax` | MiniMax M2.7 | long sessions, tool-heavy prompts, prefix reuse |
| `us4_adapter_glm` | GLM-5.1, GLM-5 | long-horizon reasoning, engineering workloads |
| `us4_adapter_qwen_dense` | Qwen2.5, Qwen3, Qwen-Coder | dense/GQA/RoPE, long-context coding |
| `us4_adapter_llama` | Llama 3.x, Llama 4 | GQA/RoPE, dense/MoE depending on model |
| `us4_adapter_gemma` | Gemma 3, Gemma 4 | small/medium low-memory execution |
| `us4_adapter_bitnet` | BitNet b1.58 and future native ternary models | 1.58-bit, ternary kernels |
| `us4_adapter_ternary` | Generic PT-BitNet converted models | post-training ternary, low-memory optimization |

---

## Universal Runtime Architecture — V6

```text
US4 V6
├── core/              ← Universal Runtime + MLX backend
├── adapters/          ← Thin adapters + configure_mlx() / configure_speculative()
├── memory/            ← Governor v3 (hot-cold KV + ANE)
├── kv/                ← Universal KV pager + continuous batching
├── cache/             ← Prefix + SSD cold + multimodal
├── moe/               ← Expert pager + SP-MoE prefetch + sparsity-aware
├── metal/             ← Metal device + kernels
├── mlx/               ← MLX backend nativo
├── neon/              ← ARM NEON + ternary hot paths
├── ane/               ← M5+ ANE probe/offload
├── tuning/            ← Auto-tuner + hardware profiles
└── telemetry/         ← Metrics + correctness validation
```

---

## Required Project Structure

```text
us4-v6-simplicio/
  CMakeLists.txt
  README.md

  runtime/
    core/
      us4_runtime_v6.cpp
      us4_runtime_v6.h
      us4_scheduler_v6.cpp
      us4_scheduler_v6.h
      us4_model_registry_v6.cpp
      us4_model_registry_v6.h
      us4_adapter_dispatcher.cpp
      us4_adapter_dispatcher.h

    adapters/
      deepseek/
        us4_adapter_deepseek_moe.cpp
        us4_adapter_deepseek_moe.h
      kimi/
        us4_adapter_kimi_moe.cpp
        us4_adapter_kimi_moe.h
      minimax/
        us4_adapter_minimax.cpp
        us4_adapter_minimax.h
      glm/
        us4_adapter_glm.cpp
        us4_adapter_glm.h
      qwen/
        us4_adapter_qwen_dense.cpp
        us4_adapter_qwen_dense.h
      llama/
        us4_adapter_llama.cpp
        us4_adapter_llama.h
      gemma/
        us4_adapter_gemma.cpp
        us4_adapter_gemma.h
      bitnet/
        us4_adapter_bitnet.cpp
        us4_adapter_bitnet.h
      ternary/
        us4_adapter_ternary.cpp
        us4_adapter_ternary.h

    memory/
      us4_governor_v3.cpp
      us4_governor_v3.h
      us4_hot_cold_memory.cpp
      us4_hot_cold_memory.h
      us4_low_ram_degradation.cpp
      us4_low_ram_degradation.h

    kv/
      us4_kv_pager_v6.cpp
      us4_kv_pager_v6.h
      us4_kv_continuous_batching.cpp
      us4_kv_continuous_batching.h
      us4_kv_hot_cold.cpp
      us4_kv_hot_cold.h
      us4_kv_layout_adapter.cpp
      us4_kv_layout_adapter.h

    cache/
      us4_prefix_cache_v6.cpp
      us4_prefix_cache_v6.h
      us4_ssd_cold_cache.cpp
      us4_ssd_cold_cache.h
      us4_session_checkpoint.cpp
      us4_session_checkpoint.h
      us4_multimodal_cache.cpp
      us4_multimodal_cache.h

    moe/
      us4_expert_pager_v6.cpp
      us4_expert_pager_v6.h
      us4_sp_moe_prefetch.cpp
      us4_sp_moe_prefetch.h
      us4_sparsity_expert_cache.cpp
      us4_sparsity_expert_cache.h
      us4_expert_routing_telemetry.cpp
      us4_expert_routing_telemetry.h

    metal/
      us4_metal_device.mm
      us4_metal_device.h
      us4_metal_heap_pool.mm
      us4_metal_heap_pool.h
      us4_metal_scheduler.mm
      us4_metal_scheduler.h
      us4_kernels_v6.metal

    mlx/
      us4_mlx_backend.mm
      us4_mlx_backend.h
      us4_mlx_graph_fusion.mm
      us4_mlx_graph_fusion.h
      us4_mlx_zero_copy.mm
      us4_mlx_zero_copy.h
      us4_mlx_lazy_eval.mm
      us4_mlx_lazy_eval.h

    neon/
      us4_neon_dequant.cpp
      us4_neon_dequant.h
      us4_neon_kv.cpp
      us4_neon_kv.h
      us4_neon_ternary.cpp
      us4_neon_ternary.h

    ane/
      us4_ane_probe.mm
      us4_ane_probe.h
      us4_ane_offload_planner.mm
      us4_ane_offload_planner.h

    speculative/
      us4_peagle.cpp
      us4_peagle.h
      us4_eagle3.cpp
      us4_eagle3.h
      us4_draft_tree.cpp
      us4_draft_tree.h

    tuning/
      us4_autotune_v6.cpp
      us4_autotune_v6.h
      us4_hardware_probe_v6.cpp
      us4_hardware_probe_v6.h
      us4_profile_store_v6.cpp
      us4_profile_store_v6.h

    telemetry/
      us4_metrics_v6.cpp
      us4_metrics_v6.h
      us4_trace_v6.cpp
      us4_trace_v6.h
      us4_correctness.cpp
      us4_correctness.h
      us4_logit_drift.cpp
      us4_logit_drift.h

    benchmarks/
      us4_bench_macbook_matrix.cpp
      us4_bench_adapters.cpp
      us4_bench_mlx.cpp
      us4_bench_moe.cpp
      us4_bench_kv_batching.cpp
      us4_bench_ternary.cpp
      us4_bench_speculative.cpp
      us4_bench_end_to_end.cpp

  profiles/
    hardware/
      macbook_128gb.json
      macbook_96gb.json
      macbook_64gb.json
      macbook_48gb.json
      macbook_32gb.json
      macbook_24gb.json
      macbook_16gb.json

    models/
      deepseek_v4_flash.json
      kimi_k2_6.json
      minimax_m2_7.json
      glm_5_1.json
      qwen_dense.json
      llama.json
      gemma.json
      bitnet.json
      ternary_generic.json

  docs/
    us4-v6-architecture.md
    us4-v6-adapter-design.md
    us4-v6-mlx-backend.md
    us4-v6-moe-prefetch.md
    us4-v6-continuous-batching.md
    us4-v6-ternary.md
    us4-v6-macbook-matrix.md
    us4-v6-benchmark-methodology.md
```

---

## Adapter Interface — V6

Every adapter must implement:

```cpp
class IUS4V6Adapter {
public:
    virtual ~IUS4V6Adapter() = default;

    virtual const char* family() const = 0;
    virtual const char* model_name() const = 0;
    virtual US4ArchitectureType architecture_type() const = 0;

    virtual bool supports_moe() const = 0;
    virtual bool supports_mla() const = 0;
    virtual bool supports_gqa() const = 0;
    virtual bool supports_multimodal() const = 0;
    virtual bool supports_ternary() const = 0;
    virtual bool supports_mlx_backend() const = 0;
    virtual bool supports_speculative_decoding() const = 0;

    virtual US4KVLayout kv_layout() const = 0;

    virtual US4QuantStrategy recommended_quant_strategy(
        const US4HardwareProfile& hardware
    ) const = 0;

    virtual US4MemoryPlan build_memory_plan(
        const US4HardwareProfile& hardware,
        US4RuntimeMode mode
    ) const = 0;

    virtual bool configure_mlx(US4MLXContext& mlx) = 0;
    virtual bool configure_speculative(US4SpeculativeContext& speculative) = 0;
    virtual bool configure_runtime(US4RuntimeContext& context) = 0;
};
```

---

## Runtime Modes — V6

```cpp
enum class US4RuntimeMode {
    FULL,
    BALANCED_PLUS,
    DEGRADED,
    ULTRA_LOW,
    MICRO,
    MICRO_PLUS,
    NANO
};
```

Mapping:

```text
128GB -> FULL
96GB  -> BALANCED_PLUS
64GB  -> DEGRADED
48GB  -> ULTRA_LOW
32GB  -> MICRO
24GB  -> MICRO_PLUS
16GB  -> NANO
```

---

## MacBook Compatibility Matrix — V6

| MacBook RAM | US4 V6 Mode | Frontier MoE: DeepSeek/Kimi/MiniMax/GLM | Qwen/Llama 14B–32B | Qwen/Gemma 3B–9B | BitNet/Ternary |
|---:|---|---|---|---|---|
| **128GB** | Full | Good / limited | Excellent | Excellent | Excellent |
| **96GB** | Balanced+ | Limited viable | Excellent | Excellent | Excellent |
| **64GB** | Degraded | Experimental | Good / strong | Excellent | Excellent |
| **48GB** | Ultra-Low | Laboratory | Viable | Very good | Excellent |
| **32GB** | Micro | No | Limited | Good | Excellent |
| **24GB** | Micro+ | No | Not recommended | Good with 3B/4B | Excellent |
| **16GB** | Nano | No | No | 1B–3B only | Good |

---

## Backend Selection Strategy

US4 V6 must choose backend dynamically:

```text
Preferred backend order:
1. MLX native backend
2. Metal optimized backend
3. Metal + NEON hybrid
4. NEON CPU fallback
5. Safe scalar fallback
```

Rules:

```text
Use MLX when:
- model adapter supports MLX
- zero-copy unified memory improves memory behavior
- graph fusion is available
- correctness validation passes

Use Metal when:
- operation is GPU-heavy
- fused kernels outperform MLX path
- adapter has custom Metal kernels

Use NEON when:
- dequantization/compression is CPU-side hot path
- model is small enough for CPU-assisted execution
- ternary/BitNet path benefits from SIMD

Use ANE when:
- M5+ hardware is detected
- op is lightweight and supported
- offload reduces power or improves concurrency
```

---

## MLX Backend Requirements

Implement MLX backend with:

```text
zero-copy unified memory
lazy evaluation hooks
graph fusion
adapter-specific tensor layout
MLX fallback to Metal when needed
memory pressure awareness
```

Acceptance criteria:

```text
MLX path must be optional.
MLX path must be benchmarked against Metal path.
MLX path must pass correctness validation.
MLX must not increase active memory unexpectedly.
```

---

## SP-MoE / Speculative Expert Prefetch Requirements

For MoE adapters:

```text
DeepSeek
Kimi
MiniMax
future MoE adapters
```

Implement expert prediction based on:

```text
recent routing history
hidden state summaries
layer-level expert patterns
token position
session type
adapter-specific routing statistics
hardware memory mode
```

Expose:

```cpp
class US4SpeculativeExpertPrefetcher {
public:
    bool predict_next_experts(
        const US4RoutingHistory& history,
        US4ExpertPrediction* output,
        size_t max_predictions
    );

    bool prefetch_experts(
        const US4ExpertPrediction* predictions,
        size_t count
    );

    US4ExpertPrefetchStats stats() const;
};
```

Acceptance criteria:

```text
Must measure:
- prefetch hit rate
- false prefetch rate
- expert page fault latency
- RAM impact
- tokens/s impact
```

---

## Continuous Batching Requirements

US4 V6 must support multi-session execution.

Continuous batching should group compatible decode steps across sessions.

Must support:

```text
multi-session batching
KV isolation per session
shared prefix reuse
hot-cold KV migration
session priority
backpressure
```

Acceptance criteria:

```text
No cross-session KV corruption.
No prompt leakage.
Batching must be disableable.
Batching must improve multi-session throughput in benchmarks.
```

---

## Hot-Cold Dual-Layer KV

KV cache must be tiered:

```text
HOT:
  active KV in unified memory

WARM:
  compressed KV in memory

COLD:
  SSD-backed KV pages

SUMMARY:
  compressed session state when full KV is not needed
```

Rules:

```text
Recent tokens stay hot.
Reusable prefixes stay warm.
Old inactive KV becomes cold.
Low-value session context becomes summary.
```

---

## Ternary / PT-BitNet Adapter

V6 introduces:

```text
us4_adapter_ternary
```

Purpose:

```text
Support models converted through post-training ternary quantization.
Support native BitNet-style ternary models.
Optimize 1.58-bit packing, unpacking and matrix operations.
```

NEON hot paths:

```text
ternary unpack
ternary dot product
ternary accumulation
ternary-to-fp16 conversion
```

Future V7 may add:

```text
handwritten assembly for ternary hot paths
```

---

## P-EAGLE / EAGLE-3 Speculative Decoding

Implement optional speculative decoding:

```text
draft model
parallel draft tree
verification path
adapter-specific enable/disable
correctness guardrail
```

Acceptance criteria:

```text
Must be optional.
Must measure accepted draft ratio.
Must measure rejected draft ratio.
Must not corrupt output.
Must fallback safely when acceptance rate is low.
```

---

## ANE Offload — M5+

Implement ANE offload detection.

Candidate tasks:

```text
embedding lookup helpers
small projection layers
softmax candidates
routing predictor
expert prefetch predictor
lightweight draft predictor
```

Acceptance criteria:

```text
ANE offload must be optional.
ANE offload must be benchmarked.
ANE offload must not increase latency.
ANE offload must fallback automatically.
```

---

## CLI Design

Example:

```bash
./us4 \
  --model models/kimi-k2.6 \
  --adapter kimi-moe \
  --mode auto \
  --backend auto \
  --enable-mlx \
  --enable-metal \
  --enable-neon \
  --enable-ane-auto \
  --enable-continuous-batching \
  --enable-sp-moe-prefetch \
  --enable-hot-cold-kv \
  --enable-ssd-cache \
  --enable-speculative-decoding \
  --metrics
```

Auto mode:

```bash
./us4 \
  --model models/glm-5.1 \
  --adapter auto \
  --mode auto \
  --backend auto \
  --autotune \
  --metrics
```

Expected startup output:

```text
US4 V6 Universal State Runtime Enabled
Build: us4-v6-simplicio
Detected Hardware: Apple Silicon
Unified Memory: XX GB
Runtime Mode: Full / Balanced+ / Degraded / Ultra-Low / Micro / Micro+ / Nano
Model: <model>
Detected Family: <family>
Adapter: <adapter>
Architecture: <Dense / MoE / MLA / GQA / Ternary>
Backend: MLX / Metal / Metal+NEON / NEON
MLX: Enabled / Disabled
Metal: Enabled / Disabled
NEON: Enabled / Disabled
ANE Offload: Enabled / Unsupported / Disabled
Continuous Batching: Enabled
Hot-Cold KV: Enabled
SSD Cold Cache: Enabled
Speculative Expert Prefetch: Enabled / Not Applicable
Speculative Decoding: Enabled / Disabled
AutoTune Profile: Loaded / Not Found
Metrics: Enabled
```

---

## Benchmarks

Required benchmarks:

```text
startup time
time-to-first-token
tokens/s
active RAM
peak RAM
SSD read/write
KV page faults
expert page faults
prefix cache hit rate
repeated prefill improvement
adapter overhead
MLX time
Metal time
NEON time
ANE time where applicable
continuous batching throughput
speculative decoding acceptance rate
logit drift
```

Benchmark MacBook profiles:

```text
128GB
96GB
64GB
48GB
32GB
24GB
16GB
```

Benchmark model classes:

```text
frontier_moe
large_dense
medium_dense
small_dense
ternary
multimodal
```

---

## Correctness Rules

Every optimization must be disableable.

Every adapter must support correctness validation:

```text
same prompt
same seed / greedy mode
baseline output comparison
logit drift measurement
KV layout validation
adapter fallback path
backend fallback path
```

If drift exceeds threshold:

```text
disable aggressive optimization
fallback to safer path
log reason
continue execution
```

---

## Development Order

Implement in this order:

```text
1. US4 V6 core runtime skeleton
2. Hardware profile detection
3. Model registry
4. Adapter interface
5. Backend selector
6. Qwen/Gemma small dense adapter
7. BitNet adapter
8. Ternary adapter
9. Llama adapter
10. MLX backend
11. Metal backend integration
12. NEON hot paths
13. Universal KV pager
14. Hot-cold KV
15. Prefix cache
16. SSD cold cache
17. Continuous batching
18. DeepSeek MoE adapter
19. Kimi MoE adapter
20. MiniMax adapter
21. GLM adapter
22. SP-MoE prefetch
23. P-EAGLE / EAGLE-3 speculative decoding
24. ANE offload probe
25. Auto-tuning
26. MacBook simulation benchmark
27. End-to-end benchmark
28. Documentation
29. Final report
```

Start with small dense models to validate the universal core.

Do not start with the largest MoE models.

---

## PR Requirements

Each PR must include:

```text
problem statement
adapter affected
hardware profile used
benchmark method
before/after results
correctness notes
known limitations
rollback path
```

No PR may claim universal performance wins without benchmark evidence.

---

## Final Positioning

```text
DS4 optimizes one model.
US4 V6 optimizes many model families through specialized adapters and 2026 hardware-aware backends.

US4 V6 is not generic inference.
US4 V6 is specialized inference by architecture.
```

Final tagline:

> **US4 V6: Universal core, specialized adapters + 2026 SOTA, local LLMs optimized for real MacBooks.**
