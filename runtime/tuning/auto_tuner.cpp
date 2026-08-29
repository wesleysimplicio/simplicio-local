#include "tuning/auto_tuner.h"

#include <algorithm>
#include <cmath>

namespace us4 {

AutoTunerProfile
SelectAutoTunerProfile(const HardwareProbeResult &hardware,
                       const std::vector<AutoTunerCandidate> &candidates) {
  AutoTunerProfile profile;
  profile.chip = hardware.chip;
  if (candidates.empty()) {
    return profile;
  }
  auto best = std::min_element(
      candidates.begin(), candidates.end(),
      [](const AutoTunerCandidate &lhs, const AutoTunerCandidate &rhs) {
        if (lhs.observedLatencyMs != rhs.observedLatencyMs) {
          return lhs.observedLatencyMs < rhs.observedLatencyMs;
        }
        if (lhs.batchSize != rhs.batchSize) {
          return lhs.batchSize > rhs.batchSize;
        }
        if (lhs.tileRows != rhs.tileRows) {
          return lhs.tileRows > rhs.tileRows;
        }
        return lhs.tileCols > rhs.tileCols;
      });
  profile.tileRows = best->tileRows;
  profile.tileCols = best->tileCols;
  profile.batchSize = best->batchSize;
  profile.estimatedLatencyMs = best->observedLatencyMs;
  return profile;
}

BoundedTuningResult RunBoundedAutoTune(
    const HardwareProbeResult &hardware,
    const std::vector<AutoTunerCandidate> &candidates,
    const AutoTunerBenchmark &benchmark, const BoundedTuningConfig &config) {
  (void)hardware;
  BoundedTuningResult result;
  if (!benchmark || config.maxCandidates == 0U ||
      config.maxRunsPerCandidate == 0U || config.maxStartupMs <= 0.0F) {
    result.reason = "invalid-bounded-tuning-config";
    return result;
  }
  const auto scalar = std::find_if(
      candidates.begin(), candidates.end(),
      [](const AutoTunerCandidate &candidate) {
        return candidate.name == "scalar";
      });
  if (scalar == candidates.end()) {
    result.reason = "portable-scalar-candidate-missing";
    return result;
  }
  const AutoTunerObservation baseline = benchmark(*scalar);
  result.observations.push_back(baseline);
  if (!baseline.completed || !baseline.correct || baseline.runs == 0U ||
      baseline.runs > config.maxRunsPerCandidate ||
      !std::isfinite(baseline.p50LatencyMs) ||
      !std::isfinite(baseline.p95LatencyMs) || baseline.p50LatencyMs <= 0.0F ||
      baseline.p95LatencyMs <= 0.0F) {
    result.reason = "invalid-scalar-baseline";
    return result;
  }
  float bestLatencyMs = baseline.p50LatencyMs;
  const std::size_t limit = std::min(config.maxCandidates, candidates.size());
  for (std::size_t index = 0U; index < candidates.size() && index < limit;
       ++index) {
    const AutoTunerCandidate &candidate = candidates[index];
    if (candidate.name == "scalar" || candidate.observedLatencyMs > config.maxStartupMs) {
      continue;
    }
    const AutoTunerObservation observation = benchmark(candidate);
    result.observations.push_back(observation);
    if (observation.kernel != candidate.name || !observation.completed ||
        !observation.correct || observation.runs == 0U ||
        observation.runs > config.maxRunsPerCandidate ||
        !std::isfinite(observation.p50LatencyMs) ||
        !std::isfinite(observation.p95LatencyMs) ||
        observation.p50LatencyMs <= 0.0F || observation.p95LatencyMs <= 0.0F) {
      continue;
    }
    const bool faster = observation.p50LatencyMs <
                        baseline.p50LatencyMs * (1.0F - config.minimumSpeedup);
    const bool p95Safe = observation.p95LatencyMs <=
                         baseline.p95LatencyMs * (1.0F + config.maxP95Regression);
    if (faster && p95Safe && observation.p50LatencyMs < bestLatencyMs) {
      result.selectedKernel = candidate.name;
      result.promoted = true;
      result.reason = "bounded-autotune-promoted";
      bestLatencyMs = observation.p50LatencyMs;
    }
  }
  if (!result.promoted) {
    result.reason = "no-candidate-beat-safe-baseline";
  }
  return result;
}

} // namespace us4
