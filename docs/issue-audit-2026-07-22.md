# Simplicio-local issue audit — 2026-07-22

This is the reproducible inventory for meta-audit issue #151. It records the
state of every issue in the repository, the implementation evidence available
on `main`, and the reason an item remains open. An issue is not marked done
because its description exists; it needs an implementation, a test, and
observable evidence.

## Repository snapshot

| Field | Value |
|---|---|
| Repository | `wesleysimplicio/simplicio-local` |
| Default branch | `main` |
| Audit date | 2026-07-22 |
| Audited main SHA | `5408dfc5f4275a57d37966872cd38cd95f1d0603` |
| Open issues after this audit | 16 |
| Merged issue-linked deliveries in this cycle | #124 partial, #125, #145, #148 |
| Local runtime CMake build | `null` — `cmake` is not installed in the execution environment |
| Apple Metal/MLX/ANE evidence | `null` — no Apple Silicon/macOS host is available |
| Real 16 GB GLM-5.2 evidence | `null` — no 16 GB host or ~370 GB checkpoint is available |

## Evidence captured

The following checks were run locally and are safe to reproduce without
network access or paid CI:

```text
npm run lint                              PASS
npm test -- --coverage                    26 passed, 0 failed, 88.16% lines
engine/c make test-tokenizer              4/4 encode, 4/4 round-trip
engine/c make test                       3 C tests + tokenizer + 53 Python PASS
engine/c make sanitize                    C ASan/UBSan PASS; oracle explicitly skipped
seed_quant_fuzz_corpus.py                 100 real-weight slices per int width
quantization AFL driver corpus smoke      PASS for all generated seeds and edge cases
```

The sanitizer oracle fixture is intentionally reported as unavailable rather
than fabricated. `make sanitize SANITIZE_REQUIRE_ORACLES=1` fails with an
actionable message until the generated GLM and DeepSeek fixtures exist.

## Issue inventory

| Issue | State | Scope | Evidence / remaining work |
|---:|---|---|---|
| #81 | OPEN | Apple Silicon inference epic | `PARTIAL`: native CPU/runtime pieces exist; completion depends on real Metal/MLX/ANE and end-to-end model evidence. |
| #86 | OPEN | NEON/Metal/MLX real backends | `BLOCKED`: requires macOS Apple Silicon and a real GPU/MLX trace; no simulation is accepted as completion. |
| #116 | OPEN | CPU-only any-LLM on 16 GB epic | `PARTIAL`: colibri engine, profile, routing, and contracts exist; real 16 GB proof and all milestones remain. |
| #118 | OPEN | 16 GB GLM-5.2 baseline | `BLOCKED`: requires a real 16 GB host, ≥400 GB SSD, and the real checkpoint. |
| #121 | OPEN | Kimi K2 family | `PENDING`: tiny/config documentation exists; real tokenizer, converter, oracle, and 16 GB execution remain. |
| #122 | OPEN | Buffer safety and engine fuzzing | `PARTIAL`: buffer inventory, ASan/UBSan target, parser fuzz infrastructure, and explicit fixture gating exist. Four C-engine harnesses, adversarial config suite, and a recorded one-hour campaign remain. |
| #123 | OPEN | Family tokenizer/chat-template parity | `PARTIAL`: byte-level tokenizer contract is covered; DeepSeek/Kimi family templates and committed HF parity vectors remain. |
| #124 | OPEN | Forward/tokenizer/quantization test suite | `PARTIAL`: `test_tok` is now in `make test` via merged PR #155; three-family forward fixtures, `test_quant`, KV persistence, and speculative losslessness remain. |
| #125 | CLOSED | CI matrix, sanitizers, fuzz schedule | `DONE`: merged PR #154 (`0d45fbcc7200abb6ad1e28b4e6a80e6fcb27c9b3`) runs runtime quick checks on PR/push and quantization fuzz on schedule. |
| #126 | OPEN | Reproducible benchmarks/perplexity | `PARTIAL`: benchmark harness and schema exist; real-model perplexity, quality cost, and comparative measurements remain. |
| #128 | OPEN | CPU kernel optimization | `PENDING`: optimization is measurement-gated; stable cross-ISA profiling and before/after data are not available. |
| #129 | OPEN | Expert cache/speculative decoding | `PARTIAL`: cache/pin/speculative code exists; 16 GB hit-rate, tok/s, and adaptive-policy evidence remain. |
| #130 | OPEN | Dense layer streaming | `PENDING`: no complete dense-stream executor and real slow-path demonstration yet. |
| #131 | OPEN | Unified CLI/serve/UI/E2E | `PARTIAL`: CLI/native server contracts exist; one product surface backed by the real engine and complete E2E evidence remains. |
| #142 | OPEN | Governed ecosystem integration | `PENDING`: the Runtime/Loop admission, resource reservation, cancellation, and typed receipt boundary is not complete in this repository. |
| #143 | OPEN | Prototype-first local worker | `PENDING`: capability/schema/escalation worker integration with Loop/Runtime/Agent/Code remains. |
| #145 | CLOSED | Quantization-kernel fuzzing | `DONE`: merged PR #152 (`f82fa5c6622e00478512b0dc1f1ffd0c3a9f7644`) adds int4/int8 scalar-oracle targets, AFL++ driver, and real-weight-derived corpus generation. |
| #148 | CLOSED | CI trigger/coverage audit | `DONE`: merged PR #153 (`060dea41259b32244633dfddf2754fe2381f4687`) enables triggers, enforces ≥80% starter coverage, fixes the repository guard, and adds workflow tests. |
| #151 | OPEN | This meta-audit | This document supplies the inventory and explicit residual decisions; it can close after the report is published. |

## Decision rules for the remaining slots

1. `DONE` requires an implementation, a reproducible local test, and a linked
   PR/commit.
2. `PARTIAL` remains open until its stated acceptance criteria are met.
3. `BLOCKED` remains open when the acceptance criteria explicitly require
   hardware, checkpoints, or measurements unavailable in this environment.
4. Unobservable metrics are `null` with a reason; they are never estimated.
5. Every future implementation must use a branch and PR targeting `main` and
   must add regression evidence before closing its issue.

This report intentionally does not claim that the remaining hardware- and
measurement-dependent issues are complete.
