#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>

#include "core/model_asset.h"

namespace us4 {

enum class DFlashQuantization {
  kUnknown,
  kFp16,
  kInt8,
  kInt4,
  kInt2,
};

struct DFlashDescriptor {
  std::string family;
  std::string targetFamily;
  std::string targetModel;
  std::string tokenizerHash;
  std::string filePath;
  DFlashQuantization quantization = DFlashQuantization::kUnknown;
  std::string backend;
  std::size_t maxDraftTokens = 1;
  std::size_t estimatedMemoryGiB = 0;
};

struct DFlashCapability {
  bool supported = false;
  std::string evidence;
  std::string reason;
};

struct DFlashCompatibilityRequest {
  std::string targetFamily;
  std::string targetModel;
  std::string targetTokenizerHash;
  std::string targetBackend;
  std::size_t availableMemoryGiB = 0;
  bool allowQuantizedDraft = true;
};

struct DFlashCompatibilityResult {
  bool compatible = false;
  std::string placement;
  std::string reason;
};

struct DFlashTelemetry {
  std::size_t draftAttempts = 0;
  std::size_t acceptedTokens = 0;
  std::size_t rejectedTokens = 0;
  double acceptanceRate = 0.0;
  double draftTokensPerSecond = 0.0;
  double targetTokensPerSecond = 0.0;
};

std::string_view ToString(DFlashQuantization quantization);
bool ParseDFlashQuantization(std::string_view value,
                             DFlashQuantization *quantization);

std::optional<DFlashDescriptor> ParseDFlashManifestBody(
    const std::string &manifestBody);

DFlashCapability DiscoverDFlashCapability(const ModelAsset &asset,
                                          std::string_view backend);

DFlashCompatibilityResult ValidateDFlashCompatibility(
    const DFlashDescriptor &draft, const DFlashCompatibilityRequest &request);

DFlashTelemetry ComputeDFlashTelemetry(std::size_t draftAttempts,
                                       std::size_t acceptedTokens,
                                       double draftTokensPerSecond,
                                       double targetTokensPerSecond);

} // namespace us4
