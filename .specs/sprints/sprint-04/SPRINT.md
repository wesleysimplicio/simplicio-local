---
sprint: sprint-04
status: todo
start: 2026-06-25
end: 2026-07-08
owner: us4-core
---

# Sprint 04 — NEON Hot Paths (Apple)

## Objetivo
Caminhos quentes em NEON (ARM SIMD): matmul, attention, dequantizacao INT8/INT4. Block GEMM tipo BLAS.

## Tasks
- [ ] T04.1 — `runtime/neon/neon_matmul.cpp` (FP16/BF16/INT8 via dotprod, vdotq_s32)
- [ ] T04.2 — `runtime/neon/neon_attention.cpp` (causal, fused softmax-rescale)
- [ ] T04.3 — `runtime/neon/dequant_int8.cpp` + `dequant_int4.cpp` (group-wise scales)
- [ ] T04.4 — Block GEMM tiling 8x8 / 4x16 + cache-aware prefetch
- [ ] T04.5 — Auto-select NEON vs scalar via probe (vector width, cluster type P/E)
- [ ] T04.6 — Re-bench Qwen/Gemma com NEON vs scalar

## Test plan
- Unit: NEON matmul vs scalar (atol 1e-3 BF16); dequant INT8 vs FP32 ground truth.
- Regression: Sprint 01-03 verde.
- E2E: `us4-cli run --backend neon` >=2x speedup vs scalar baseline.
- Correctness: diff NEON vs scalar <= 1e-3.

## DoD
- NEON path em DEGRADED + ULTRA_LOW modes.
- Coverage >=80% em `runtime/neon`.
- Bench tabela atualizada com numeros NEON.

## Riscos
- E-core throttling em workloads sustained -> stick com P-core para hot path.
