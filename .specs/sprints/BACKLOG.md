# Backlog — US4 V6 Apple Edition

Universal State Runtime for local LLM inference on Apple Silicon (M1–M5+).
Stack: C++17/20 + MLX + Metal + NEON + ANE (M5+) + CMake + GoogleTest + Playwright (CLI/UX) + Ralph Loop.

Reference master spec: `../../US4-V6-simplicio.md`.

## Cadence
- Sprint length: 2 weeks. 12 sprints total.
- DoD gate: lint + unit (>=80% cov on touched code) + Playwright E2E + correctness diff vs reference within tolerance.
- Loop: read -> plan -> edit -> lint -> unit -> e2e -> regression -> ralph fix -> commit.

## Sprint Matrix

| Sprint | Theme | Key Deliverables | Adapters | Backends |
|---|---|---|---|---|
| 01 | Foundations & Skeleton | Project scaffolding, core runtime contracts, hardware probe, mode selector, telemetry skeleton, CI/DoD pipeline | — | — |
| 02 | CPU Scalar Baseline | C++ tensor primitives, scalar matmul, scalar attention, dense adapter base, smoke benchmark | Qwen dense, Gemma | CPU scalar |
| 03 | MLX + Metal Skeleton | MLX integration, Metal command queue, Metal matmul kernels, unified-memory KV, MLX<->C++ bridge | Qwen, Gemma | MLX, Metal |
| 04 | NEON Hot Paths | NEON matmul, NEON attention, NEON dequant (INT8/INT4), block GEMM | Qwen, Gemma | CPU NEON |
| 05 | BitNet + Ternary | BitNet 1.58-bit kernels, PT-BitNet ternary adapter, ternary lookup tables, MICRO mode | BitNet, Ternary | Metal, NEON |
| 06 | KV Memory Architecture | Hot-cold KV pager, prefix cache, SSD cold tier, KV summarization, eviction policies | All current | Metal, NEON |
| 07 | Llama Adapter | Llama 3/4 adapter, GQA, RoPE scaling, ALiBi optional, full attention path | Llama | All |
| 08 | MoE Foundation | DeepSeek MoE adapter, Kimi MoE adapter, expert pager, expert offload to RAM, top-k routing | DeepSeek, Kimi | Metal, NEON |
| 09 | MoE Advanced | MiniMax adapter, GLM adapter, SP-MoE speculative expert prefetch, sparsity-aware cache, multimodal cache | MiniMax, GLM | Metal, NEON, MLX |
| 10 | Batching + Speculative | Continuous batching multi-session, P-EAGLE / EAGLE-3 speculative decoding, draft model loader | All | All |
| 11 | ANE M5+ Offload | ANE backend, dense layer offload to ANE, mixed dispatch (Metal+ANE), ANE thermal/throttle policy | Dense (Qwen/Gemma/Llama) | ANE |
| 12 | Auto-Tune + Release v1.0 | Hardware-aware auto-tuning, benchmark matrix (7 RAM tiers x 9 adapters), CLI polish, docs final, release | All | All |

## Cross-Cutting (every sprint)
- Unit tests (GoogleTest) on every new public API.
- Regression suite re-run on existing adapters + modes.
- Playwright E2E on CLI flows + telemetry surface (trace+screenshot+video).
- Ralph Loop autonomous run after merge to validate green.
- Correctness diff vs reference impl logged in `runtime/benchmarks/correctness/`.
- Telemetry expand: latency, tokens/s, RAM/VRAM peak, KV hit-rate, expert hit-rate, mode transitions.

## Definition of Ready
- Linked to master spec section.
- Acceptance criteria measurable (numeric or boolean).
- Test plan declared (unit + e2e + regression).
- Hardware profile target identified.

## Definition of Done
- Code merged via PR, conventional commit (English).
- All gates green (lint/unit/e2e/regression/correctness).
- Coverage >=80% on touched files.
- ADR added if architectural decision was made.
- Changelog entry under correct version.
- Sprint-end demo recorded if user-visible.

## Out of Scope
- Cloud/distributed inference (single-machine focus).
- Training/fine-tuning (inference only).
- Non-Apple hardware on this edition (see Windows Edition).
- GUI desktop app (CLI + library only).
