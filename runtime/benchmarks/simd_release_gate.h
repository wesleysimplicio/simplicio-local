#pragma once

#include <string>

namespace us4::benchmarks {

struct SimdGateObservation {
  bool scalarCorrect = false;
  bool candidateCorrect = false;
  bool illegalInstruction = false;
  bool memorySafe = false;
  bool endToEndModel = false;
  bool benchmarkObserved = false;
  float scalarP50Ms = 0.0F;
  float scalarP95Ms = 0.0F;
  float candidateP50Ms = 0.0F;
  float candidateP95Ms = 0.0F;
};

struct SimdGateResult {
  bool accepted = false;
  std::string reason = "gate-not-evaluated";
};

SimdGateResult EvaluateSimdReleaseGate(
    const SimdGateObservation& observation, float minimumSpeedup = 0.02F,
    float maximumP95Regression = 0.10F);

}  // namespace us4::benchmarks
