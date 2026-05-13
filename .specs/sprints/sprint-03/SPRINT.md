---
sprint: sprint-03
status: todo
start: TBD
end: TBD
owner: us4-core
---

# Sprint 03 — MLX + Metal Skeleton (Apple)

## Objetivo
Integrar MLX e Metal. Command queue + kernels matmul Metal, MLX bridge, KV em memoria unificada.

## Tasks
- [ ] T03.1 — Metal device init + `runtime/metal/CommandQueue` + autorelease wrapper
- [ ] T03.2 — `runtime/metal/kernels/matmul.metal` (FP16/BF16) + dispatch wrapper
- [ ] T03.3 — `runtime/metal/kernels/{softmax,rmsnorm}.metal`
- [ ] T03.4 — MLX integration `runtime/mlx/MLXBridge` (graph build, eval, buffer share)
- [ ] T03.5 — `runtime/memory/UnifiedAllocator` (unified memory CPU+GPU)
- [ ] T03.6 — Qwen + Gemma: enable Metal path (dispatch flag)
- [ ] T03.7 — Backend selector logic (CPU/MLX/Metal) ligado a RuntimeMode

## Test plan
- Unit: matmul Metal vs scalar (atol 1e-2 FP16); softmax Metal vs scalar; MLXBridge eval.
- Regression: Sprint 02 CPU paths intactos.
- E2E: `us4-cli run --backend metal` gera 32 tokens em <=10s no M2/M3.
- Correctness: diff Metal vs CPU <= 5e-3.

## DoD
- Metal habilitado em FULL/BALANCED.
- Coverage >=80% em `runtime/metal` + `runtime/mlx`.
- ADR-003 Backend selection strategy.

## Riscos
- MLX API churn -> pinar versao no CMake.
