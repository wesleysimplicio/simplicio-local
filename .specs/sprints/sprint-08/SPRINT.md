---
sprint: sprint-08
status: todo
start: TBD
end: TBD
owner: us4-core
---

# Sprint 08 — MoE Foundation (Apple)

## Objetivo
MoE: DeepSeek + Kimi adapters. Expert pager (carrega experts on-demand). Top-k routing. Offload de experts cold pra RAM.

## Tasks
- [ ] T08.1 — `runtime/moe/Router` (top-k softmax, expert selection, load balance)
- [ ] T08.2 — `runtime/moe/ExpertPager` (page experts em unified memory, evict LRU)
- [ ] T08.3 — `runtime/adapters/deepseek/DeepSeekMoEAdapter` (config, shared experts, routed experts)
- [ ] T08.4 — `runtime/adapters/kimi/KimiMoEAdapter`
- [ ] T08.5 — Loader MoE: lazy load por expert (sharded weights)
- [ ] T08.6 — Telemetry: expert hit-rate, eviction count, router entropy

## Test plan
- Unit: router top-k correctness; pager evict re-load; load balance loss.
- Regression: dense adapters + Llama nao quebram.
- E2E: DeepSeek V2/V3 Q4 em M3 Ultra gera 100 tokens em <= 30s.
- Correctness: diff vs HF reference <= 1e-3.

## DoD
- DeepSeek + Kimi em FULL/BALANCED.
- Coverage >=80% em `runtime/moe` + adapters MoE.
- ADR-006 MoE expert paging strategy.
