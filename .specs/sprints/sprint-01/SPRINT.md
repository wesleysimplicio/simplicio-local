---
sprint: sprint-01
status: done
start: 2026-05-14
end: 2026-05-27
owner: us4-core
---

# Sprint 01 - Foundations and Skeleton

## Objective

Transition this repository from planning/bootstrap into a real runtime skeleton with a minimal executable CLI contract and the core Apple-specific planning decisions locked down.

## Sprint cut

### Must ship

- runtime skeleton directories and root build contract
- `us4-cli --version`
- `us4-cli --probe`
- hardware probe contract
- runtime mode selector contract
- CI transition plan from starter to runtime
- first runtime-facing E2E smoke definition
- core ADRs for MLX-first and runtime boundaries

### Can defer

- real inference
- real correctness diff
- real release automation

## Tasks

- [x] T01.0 - Completar Agentic Starter do repositorio
- [x] T01.1 - Create root runtime scaffold and build contract
- [x] T01.2 - Define `us4-cli` contract for `--version` and `--probe`
- [x] T01.3 - Define `IUS4V6Adapter` and runtime boundaries
- [x] T01.4 - Define `HardwareProbe` and runtime mode selection contract
- [x] T01.5 - Define telemetry skeleton and validation maturity gates
- [x] T01.6 - Plan CI/DoD transition from starter to runtime
- [x] T01.7 - Define first Playwright CLI smoke coverage
- [x] T01.8 - Land ADR-001 and ADR-002

## Test plan

For Sprint 01, required validation is:

- planning consistency
- starter/package checks still green
- task completeness for current sprint
- CLI smoke plan defined

Real correctness and regression remain out of scope until runnable inference exists.

## Done criteria

- Sprint 01 tasks all have task files
- architecture docs match the runtime instead of a generic template
- product docs and workflow docs agree on the current repo phase
- no live planning placeholders remain in canonical docs
