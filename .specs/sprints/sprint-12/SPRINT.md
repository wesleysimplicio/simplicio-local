---
sprint: sprint-12
status: todo
start: 2026-10-15
end: 2026-10-28
owner: us4-core
---

# Sprint 12 — Auto-Tune + Benchmark + Release v1.0 (Apple)

## Objetivo
Auto-tuning hardware-aware (escolha de tile size, batch size, mode por hardware). Matriz de benchmark (7 RAM tiers x 9 adapters). CLI polish. Docs finais. Release v1.0.

## Tasks
- [ ] T12.1 — `runtime/tuning/AutoTuner` (mini-bench at startup, escolhe tile/batch optimal)
- [ ] T12.2 — `runtime/tuning/profiles.json` (cached profiles por chip+RAM)
- [ ] T12.3 — Matriz de benchmark `runtime/benchmarks/matrix_runner.cpp` (7 RAM x 9 adapters)
- [ ] T12.4 — CLI polish: `us4-cli serve|run|probe|bench|tune` + JSON output
- [ ] T12.5 — Docs final: `README.md` + `.specs/architecture/{DESIGN,PATTERNS}.md` final
- [ ] T12.6 — Release v1.0: tag, changelog, signed binary universal (arm64)
- [ ] T12.7 — Migration guide + troubleshooting page

## Test plan
- Unit: auto-tuner converges; profile cache load/save.
- Regression: full matrix re-run, todos adapters/modes verdes.
- E2E: release binary smoke em M1/M2/M3/M4/(M5 sim) gera tokens com mode auto.
- Correctness: diff dentro de tolerancia em todos adapters.

## DoD
- Tag `v1.0.0` criada, binary publicado em GitHub Releases.
- Coverage total >=80%.
- README + docs finais merged.
- Demo gravado.
