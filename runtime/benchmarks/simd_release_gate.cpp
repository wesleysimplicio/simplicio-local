#include "benchmarks/simd_release_gate.h"

#include <cmath>

namespace us4::benchmarks {

SimdGateResult EvaluateSimdReleaseGate(const SimdGateObservation& observation,
                                       const float minimumSpeedup,
                                       const float maximumP95Regression) {
  SimdGateResult result;
  if (!observation.scalarCorrect || !observation.candidateCorrect) {
    result.reason = "correctness-differential-failed";
    return result;
  }
  if (observation.illegalInstruction) {
    result.reason = "illegal-instruction-observed";
    return result;
  }
  if (!observation.memorySafe) {
    result.reason = "memory-safety-gate-failed";
    return result;
  }
  if (!observation.endToEndModel) {
    result.reason = "end-to-end-model-evidence-missing";
    return result;
  }
  if (!observation.benchmarkObserved ||
      !std::isfinite(observation.scalarP50Ms) ||
      !std::isfinite(observation.scalarP95Ms) ||
      !std::isfinite(observation.candidateP50Ms) ||
      !std::isfinite(observation.candidateP95Ms) ||
      observation.scalarP50Ms <= 0.0F || observation.scalarP95Ms <= 0.0F ||
      observation.candidateP50Ms <= 0.0F || observation.candidateP95Ms <= 0.0F) {
    result.reason = "benchmark-metrics-invalid";
    return result;
  }
  if (observation.candidateP50Ms >=
      observation.scalarP50Ms * (1.0F - minimumSpeedup)) {
    result.reason = "p50-speedup-below-promotion-threshold";
    return result;
  }
  if (observation.candidateP95Ms >
      observation.scalarP95Ms * (1.0F + maximumP95Regression)) {
    result.reason = "p95-regression-exceeds-budget";
    return result;
  }
  result.accepted = true;
  result.reason = "all-correctness-benchmark-model-gates-passed";
  return result;
}

}  // namespace us4::benchmarks
