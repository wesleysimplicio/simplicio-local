#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <vector>

#include "core/hardware_probe.h"

namespace us4 {

// AutoTuner contract surface for Sprint 12.
//
// At runtime startup the tuner runs a small bench across a few candidate
// tile shapes and batch sizes, then picks the one with the lowest observed
// latency. The picked profile is deterministic for a given hardware
// snapshot and tunable through the profile cache.

struct AutoTunerCandidate {
  std::size_t tileRows = 0;
  std::size_t tileCols = 0;
  std::size_t batchSize = 0;
  float observedLatencyMs = 0.0F;
  std::string name = "candidate";
};

struct AutoTunerProfile {
  std::string chip;
  std::size_t tileRows = 0;
  std::size_t tileCols = 0;
  std::size_t batchSize = 0;
  float estimatedLatencyMs = 0.0F;
  std::size_t speculativeLookaheadTokens = 0;
  std::size_t speculativeWarmupRuns = 0;
  std::size_t learnedPinnedExperts = 0;
};

AutoTunerProfile
SelectAutoTunerProfile(const HardwareProbeResult& hardware,
                       const std::vector<AutoTunerCandidate>& candidates);

struct AutoTunerObservation {
  std::string kernel = "scalar";
  float p50LatencyMs = 0.0F;
  float p95LatencyMs = 0.0F;
  std::size_t runs = 0;
  bool correct = false;
  bool completed = false;
};

struct BoundedTuningConfig {
  std::size_t maxCandidates = 8;
  std::size_t maxRunsPerCandidate = 32;
  float maxStartupMs = 100.0F;
  float minimumSpeedup = 0.02F;
  float maxP95Regression = 0.10F;
};

struct BoundedTuningResult {
  std::string selectedKernel = "scalar";
  bool promoted = false;
  std::string reason = "scalar-fallback";
  std::vector<AutoTunerObservation> observations;
};

using AutoTunerBenchmark =
    std::function<AutoTunerObservation(const AutoTunerCandidate&)>;

BoundedTuningResult RunBoundedAutoTune(
    const HardwareProbeResult& hardware,
    const std::vector<AutoTunerCandidate>& candidates,
    const AutoTunerBenchmark& benchmark,
    const BoundedTuningConfig& config = {});

}  // namespace us4
