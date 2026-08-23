#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include "core/hardware_probe.h"
#include "core/model_asset.h"

namespace us4 {

// Stable Local-side vocabulary for strategy negotiation with Simplicio Fast.
// The baseline is deliberately part of the contract: every backend must be
// able to select it when an optimization is unavailable or unproven.
enum class SpeculativeStrategy {
  kBaseline,
  kNgramPromptLookup,
  kDraftModel,
  kDFlash,
  kMtp,
};

std::string_view ToString(SpeculativeStrategy strategy);
bool ParseSpeculativeStrategy(std::string_view value,
                              SpeculativeStrategy *strategy);

struct SpeculativeCapability {
  SpeculativeStrategy strategy = SpeculativeStrategy::kBaseline;
  bool supported = false;
  std::string evidence;
  std::string reason;
};

struct SpeculativeCapabilitySnapshot {
  static constexpr std::string_view kSchemaVersion =
      "simplicio-local.speculative-capabilities/v1";

  std::string schemaVersion{std::string(kSchemaVersion)};
  std::string modelFamily;
  std::string modelName;
  std::string backend;
  std::string backendVersion;
  std::string platform;
  std::string architecture;
  bool cpuAvailable = false;
  bool metalAvailable = false;
  bool cudaAvailable = false;
  unsigned long long availableMemoryGiB = 0;
  unsigned long long gpuMemoryGiB = 0;
  std::vector<SpeculativeCapability> capabilities;
};

struct SpeculativeExecutionRequest {
  SpeculativeStrategy requested = SpeculativeStrategy::kBaseline;
  bool allowFallback = true;
  std::size_t maxDraftTokens = 1;
  std::string workload;
};

struct SpeculativeExecutionPlan {
  SpeculativeStrategy selected = SpeculativeStrategy::kBaseline;
  SpeculativeStrategy fallback = SpeculativeStrategy::kBaseline;
  bool usesSpeculation = false;
  bool usedFallback = false;
  std::size_t maxDraftTokens = 1;
  std::string reason;
};

struct SpeculativeExecutionResult {
  SpeculativeStrategy strategy = SpeculativeStrategy::kBaseline;
  bool success = false;
  bool usedFallback = false;
  std::size_t attemptedTokens = 0;
  std::size_t acceptedTokens = 0;
  double acceptanceRate = 0.0;
  std::string error;
};

// Discover only capabilities backed by observable model metadata, files, or
// hardware probes. Unknown backend support is reported as unsupported rather
// than inferred from a model name.
SpeculativeCapabilitySnapshot DiscoverSpeculativeCapabilities(
    const ModelAsset &asset, const HardwareProbeResult &hardware,
    std::string_view backend, std::string_view backendVersion = {});

SpeculativeExecutionPlan MakeSpeculativeExecutionPlan(
    const SpeculativeCapabilitySnapshot &snapshot,
    const SpeculativeExecutionRequest &request);

} // namespace us4
