---
sprint: sprint-01
status: todo
start: TBD
end: TBD
owner: us4-core
---

# Sprint 01 — Foundations & Skeleton (Apple)

## Objetivo
Bootstrap C++ runtime skeleton, hardware probe (Apple Silicon detection M1..M5+), runtime mode selector (FULL/BALANCED/DEGRADED/ULTRA_LOW/MICRO/MICRO_PLUS), telemetry skeleton, CI/DoD pipeline.

## Tasks
- [ ] T01.1 — CMake root + `runtime/{core,adapters,memory,kv,cache,moe,metal,mlx,neon,ane,speculative,tuning,telemetry,benchmarks}` skeleton
- [ ] T01.2 — `runtime/core/IUS4V6Adapter.h` interface (load, generate, kv ops, mode hooks)
- [ ] T01.3 — `runtime/core/HardwareProbe` — detect chip (M1..M5+), unified memory size, MLX caps, ANE caps
- [ ] T01.4 — `runtime/core/RuntimeMode` enum + selector heuristics (RAM tier -> mode)
- [ ] T01.5 — `runtime/telemetry` skeleton (latency, tokens/s, RAM peak, mode transitions)
- [ ] T01.6 — `.github/workflows/{ci,dod}.yml` (clang-tidy, GoogleTest, Playwright smoke, coverage gate 80%)
- [ ] T01.7 — `.claude/hooks/{post-edit,pre-commit}.sh` (lint/format + block red commits)
- [ ] T01.8 — Playwright config + first smoke (`us4-cli --version` outputs version + chip detected)
- [ ] T01.9 — ADR-001 Adapter interface contract; ADR-002 Runtime mode definitions

## Test plan
- Unit (GoogleTest): probe returns valid chip + RAM tier; mode selector picks correct mode per RAM; telemetry records sample.
- Regression: n/a (first sprint).
- E2E (Playwright): CLI `--version`, `--probe`, `--mode auto` with trace+screenshot+video.

## DoD
- Build green on M-series mac.
- CI gates green, coverage >=80% on `runtime/core`.
- ADR-001 + ADR-002 merged.
- Demo: `us4-cli --probe` outputs chip + RAM + recommended mode.

## Riscos
- Detecao de chip M5+ via `sysctlbyname` pode falhar em macOS antigo -> fallback graceful.
- MLX headers podem nao estar em todo CI runner -> mock probe quando ausente.
