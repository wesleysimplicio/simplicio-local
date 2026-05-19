# US4 V6 - Apple Edition

> Universal State Runtime for local LLM inference on Apple Silicon.
> EN. Versao pt-BR: [README.pt-BR.md](README.pt-BR.md).

![US4 V6 Guide](us4-v6-simplicio-apple.PNG)

![US4 V6 Apple Edition promotional banner](assets/us4-v6-apple-edition-promo.png)

## Run Locally

This is the shortest path to clone, build, run, and validate the project on a local machine.

![Run US4 V6 locally](assets/local-run-flow.png)

### 1. Clone

```bash
git clone https://github.com/wesleysimplicio/us4-v6-simplicio-apple.git
cd us4-v6-simplicio-apple
```

### 2. Install Tooling

Minimum tools:

- Node.js 16.7 or newer
- npm
- CMake 3.27 or newer
- Ninja
- a C++20 compiler

Recommended on macOS:

```bash
xcode-select --install
brew install cmake ninja node
npm ci
npx playwright install
```

Recommended on Windows:

```powershell
npm ci
npx playwright install
```

On Windows, run native CMake commands from a Visual Studio Developer shell when available.

### 3. Configure And Build

macOS/Linux:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

Windows PowerShell:

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

If Ninja is not available, CMake may use your platform default generator. Keep the same `build` directory.

### 4. Run The CLI

macOS/Linux:

```bash
./build/apps/us4-cli --probe
./build/apps/us4-cli run --model qwen-0.5b --prompt "hi" --max-tokens 8
./build/apps/us4-cli run --model qwen-0.5b --prompt "hi" --max-tokens 8 --json
```

Windows PowerShell:

```powershell
.\build\apps\us4-cli.exe --probe
.\build\apps\us4-cli.exe run --model qwen-0.5b --prompt "hi" --max-tokens 8
.\build\apps\us4-cli.exe run --model qwen-0.5b --prompt "hi" --max-tokens 8 --json
```

Useful model fixture examples:

```bash
./build/apps/us4-cli run --model-path tests/fixtures/models/qwen-0.5b/model.us4manifest --prompt "hi" --json
./build/apps/us4-cli run --model-path tests/fixtures/models/llama-3.1-8b --prompt "hello" --json
./build/apps/us4-cli run --model-path tests/fixtures/models/bitnet-b1.58-2b/model.us4manifest --backend neon --prompt "tiny" --json
```

### 5. Validate Everything

![Local validation checklist](assets/local-validation-checklist.png)

Run the fast JavaScript gates:

```bash
npm run lint
npm test -- --coverage
npm run pack:dry
```

Run native build and regression:

```bash
cmake --build build --config Release
ctest --test-dir build --output-on-failure -C Release
```

Run CLI E2E evidence:

```bash
npx playwright test --reporter=list,html tests/e2e/us4-cli.spec.ts
```

Run benchmark evidence:

macOS/Linux:

```bash
./build/runtime/benchmarks/dense_baseline
./build/runtime/benchmarks/matrix_runner
```

Windows PowerShell:

```powershell
.\build\runtime\benchmarks\dense_baseline.exe
.\build\runtime\benchmarks\matrix_runner.exe
```

### What "Working" Looks Like

- `us4-cli --probe` prints hardware/runtime capability information.
- `us4-cli run ...` prints generated fixture tokens and explicit backend telemetry.
- `ctest` reports all configured native tests passing.
- Playwright reports all CLI smoke tests passing and writes evidence to `playwright-report/` and `test-results/`.
- `dense_baseline` prints benchmark rows with requested backend, observed backend, fallback status, token count, and correctness placeholders where external references are not wired.

If GoogleTest is not installed locally, CMake still builds the smoke and native contract runner tests and prints a warning that GTest-specific tests were skipped.

## What This Repo Is

This repository contains the **US4 V6 Apple Edition** local runtime scaffold and implementation plan, plus the native C++ runtime slices built across the sprint plan.

Today the repo contains:

1. the **llm-project-mapper/bootstrap layer** used to scaffold disciplined AI-assisted work;
2. the **project plan** under `.specs/`;
3. the native runtime scaffold under `runtime/`;
4. the CLI under `apps/cli`;
5. unit, native contract, Playwright, and benchmark evidence paths.

Reference source: [US4-V6-simplicio.md](US4-V6-simplicio.md).

## Product scope

US4 V6 Apple Edition targets local inference for:

- dense adapters: Qwen, Llama, Gemma;
- MoE adapters: DeepSeek, Kimi, MiniMax, GLM;
- low-memory adapters: BitNet and PT-BitNet ternary;
- Apple backends: MLX, Metal, NEON/Accelerate, and optional ANE on M5+.

The product is explicitly:

- single-machine first;
- correctness-gated before performance claims;
- CLI + library, not a GUI app;
- Apple-specific in this edition.

## Current Repo Status

**Planning and runtime scaffold are now present at the project level.**

- Product docs define vision, domain, personas, runtime modes, and compatibility targets.
- Architecture docs define the runtime boundaries, contracts, and coding patterns for C++/Metal/MLX work.
- Workflow docs define how implementation moves through task, DoD, PR, and release gates.
- Runtime code, CLI, fixtures, benchmarks, and E2E tests are present.
- GitHub issues are synchronized with the local sprint task files.

## Stack

- C++20 + CMake + Ninja
- MLX as primary tensor/runtime path on Apple Silicon
- Metal for measured hot kernels not well covered by MLX
- NEON / Accelerate as CPU fallback
- ANE as opt-in offload path on M5+
- GoogleTest + CTest for unit and regression
- Playwright for CLI E2E evidence

## Working model

The repo follows the `AGENTS.md` ecosystem. Core instructions live in:

- [AGENTS.md](AGENTS.md)
- [CLAUDE.md](CLAUDE.md)
- [.github/copilot-instructions.md](.github/copilot-instructions.md)

All technical work is expected to follow the loop:

`read task -> plan -> edit -> format/lint -> unit -> e2e -> regression -> fix -> commit -> PR`

## Roadmap

| Sprint | Theme |
|---|---|
| 01 | Foundations and Skeleton |
| 02 | CPU Scalar Baseline |
| 03 | MLX and Metal Skeleton |
| 04 | NEON Hot Paths |
| 05 | BitNet and Ternary |
| 06 | KV Memory Architecture |
| 07 | Llama Adapter |
| 08 | MoE Foundation |
| 09 | MoE Advanced |
| 10 | Continuous Batching and Speculative Decoding |
| 11 | ANE M5+ Offload |
| 12 | Auto-Tune and v1.0 Release |

Details:

- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\BACKLOG.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/BACKLOG.md)
- [C:\Users\wesley.simplicio\Pictures\m\us4-v6-simplicio-apple\.specs\sprints\TIMELINE.md](C:/Users/wesley.simplicio/Pictures/m/us4-v6-simplicio-apple/.specs/sprints/TIMELINE.md)

## Repo layout today

```text
.specs/        planning source of truth
.agents/       custom agents
.skills/       reusable skills
.claude/       Claude hooks/settings
.codex/        Codex hooks/settings
.github/       starter CI/DoD and templates
apps/          native CLI entrypoint
bin/           llm-project-mapper CLI
runtime/       C++ runtime, backends, adapters, tuning, telemetry, benchmarks
test/          starter self-tests
tests/         native contract tests and Playwright CLI E2E
```

## Out of scope

- cloud or distributed inference;
- training or fine-tuning;
- non-Apple hardware in this edition;
- GUI desktop shell before CLI and library are stable.
