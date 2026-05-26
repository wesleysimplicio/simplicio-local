#!/usr/bin/env bash
# Source-based coverage gate for the native runtime.
#
# Builds the runtime + contract suite with Clang source-based coverage
# (-fprofile-instr-generate -fcoverage-mapping), runs every ctest binary while
# capturing per-process profraw, merges them with llvm-profdata, and reports
# line coverage for runtime/**/*.cpp via llvm-cov. Exits non-zero when line
# coverage falls below the threshold (default 80%, matching the DoD).
#
# Usage: scripts/coverage.sh [threshold_percent] [build_dir]
set -euo pipefail

THRESHOLD="${1:-80}"
BUILD_DIR="${2:-build-coverage}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Apple Clang ships the coverage tools behind xcrun; system LLVM exposes them
# directly (optionally version-suffixed). Resolve whatever is present.
resolve_tool() {
  local tool="$1"
  if command -v "xcrun" >/dev/null 2>&1 && xcrun --find "$tool" >/dev/null 2>&1; then
    echo "xcrun $tool"
    return 0
  fi
  local candidate
  for candidate in "$tool" "${tool}-18" "${tool}-17" "${tool}-16"; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  echo "error: could not find $tool (install llvm tools or Xcode CLT)" >&2
  return 1
}

LLVM_PROFDATA="$(resolve_tool llvm-profdata)"
LLVM_COV="$(resolve_tool llvm-cov)"

: "${CC:=clang}"
: "${CXX:=clang++}"
export CC CXX

echo "==> Configuring coverage build in $BUILD_DIR"
cmake -S . -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DUS4_BUILD_TESTS=ON \
  -DUS4_BUILD_BENCHMARKS=OFF \
  -DUS4_ENABLE_COVERAGE=ON >/dev/null

echo "==> Building"
cmake --build "$BUILD_DIR" --parallel >/dev/null

# ctest runs each binary from its own working directory, so the profile path
# must be absolute or the profraw files land in unpredictable locations.
RAW_DIR="$REPO_ROOT/$BUILD_DIR/coverage-raw"
rm -rf "$RAW_DIR"
mkdir -p "$RAW_DIR"

echo "==> Running ctest with profile capture"
LLVM_PROFILE_FILE="$RAW_DIR/%p-%m.profraw" \
  ctest --test-dir "$BUILD_DIR" --output-on-failure >/dev/null

echo "==> Merging profiles"
# shellcheck disable=SC2086
$LLVM_PROFDATA merge -sparse "$RAW_DIR"/*.profraw -o "$RAW_DIR/merged.profdata"

# Every instrumented binary must be passed to llvm-cov so its records resolve.
OBJECTS=()
for bin in \
  "$BUILD_DIR/tests/unit/us4_runtime_contract_tests" \
  "$BUILD_DIR/tests/unit/us4_runtime_smoke_test" \
  "$BUILD_DIR/tests/unit/us4_runtime_contract_runner"; do
  if [ -x "$bin" ]; then
    if [ "${#OBJECTS[@]}" -eq 0 ]; then
      OBJECTS+=("$bin")
    else
      OBJECTS+=("-object" "$bin")
    fi
  fi
done

mapfile -t RUNTIME_SOURCES < <(git ls-files 'runtime/*.cpp')

REPORT_DIR="$BUILD_DIR/coverage-report"
mkdir -p "$REPORT_DIR"

# shellcheck disable=SC2086
$LLVM_COV report "${OBJECTS[@]}" \
  -instr-profile="$RAW_DIR/merged.profdata" \
  "${RUNTIME_SOURCES[@]}" | tee "$REPORT_DIR/summary.txt"

# shellcheck disable=SC2086
$LLVM_COV export "${OBJECTS[@]}" \
  -instr-profile="$RAW_DIR/merged.profdata" \
  -format=lcov \
  "${RUNTIME_SOURCES[@]}" > "$REPORT_DIR/coverage.lcov"

LINE_PCT="$(awk '/^TOTAL/ {gsub(/%/,"",$10); print $10}' "$REPORT_DIR/summary.txt")"
echo ""
echo "Runtime line coverage: ${LINE_PCT}% (threshold ${THRESHOLD}%)"

awk -v pct="$LINE_PCT" -v thr="$THRESHOLD" 'BEGIN {
  if (pct + 0 < thr + 0) {
    printf("::error::Runtime line coverage %.2f%% is below the %s%% threshold\n", pct, thr);
    exit 1;
  }
}'
echo "Coverage gate passed."
