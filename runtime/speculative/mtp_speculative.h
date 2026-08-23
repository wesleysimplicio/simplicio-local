#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>

#include "core/model_asset.h"

namespace us4 {

struct MtpDescriptor {
  std::string family;
  std::string modelId;
  std::string tokenizerHash;
  std::string backend;
  std::string headTensor;
  std::size_t depth = 0;
};

struct MtpCapability {
  bool supported = false;
  std::size_t depth = 0;
  std::string evidence;
  std::string reason;
};

struct MtpCompatibilityRequest {
  std::string targetFamily;
  std::string targetModel;
  std::string targetTokenizerHash;
  std::string targetBackend;
};

struct MtpCompatibilityResult {
  bool compatible = false;
  std::string reason;
};

struct MtpExecutionPlan {
  bool enabled = false;
  std::size_t depth = 0;
  std::size_t maxDraftTokens = 1;
  std::string reason;
};

struct MtpTelemetry {
  std::size_t proposedTokens = 0;
  std::size_t acceptedTokens = 0;
  std::size_t rejectedTokens = 0;
  double acceptanceRate = 0.0;
};

std::optional<MtpDescriptor> ParseMtpManifestBody(
    const std::string &manifestBody);

// MTP is recognized only from explicit metadata or an actual MTP tensor
// record. Model family/name heuristics are intentionally excluded.
MtpCapability DetectMtpCapability(const ModelAsset &asset,
                                  std::string_view backend);

MtpCompatibilityResult ValidateMtpCompatibility(
    const MtpDescriptor &descriptor,
    const MtpCompatibilityRequest &request);

MtpExecutionPlan MakeMtpExecutionPlan(const MtpCapability &capability,
                                      std::size_t requestedDraftTokens);

MtpTelemetry ComputeMtpTelemetry(std::size_t proposedTokens,
                                 std::size_t acceptedTokens);

} // namespace us4
