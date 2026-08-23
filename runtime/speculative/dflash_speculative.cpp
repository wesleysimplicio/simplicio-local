#include "speculative/dflash_speculative.h"

#include <algorithm>
#include <charconv>
#include <cctype>
#include <sstream>
#include <string_view>

namespace us4 {

namespace {

std::string Trim(const std::string_view value) {
  std::size_t begin = 0;
  std::size_t end = value.size();
  while (begin < end && std::isspace(static_cast<unsigned char>(value[begin]))) {
    ++begin;
  }
  while (end > begin && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
    --end;
  }
  return std::string(value.substr(begin, end - begin));
}

bool ParseSize(const std::string &value, std::size_t *out) {
  if (out == nullptr || value.empty()) {
    return false;
  }
  const auto parsed = std::from_chars(value.data(), value.data() + value.size(), *out);
  return parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size();
}

bool IsTrue(const ModelAsset &asset, const std::string_view key) {
  const auto it = asset.metadata.find(std::string(key));
  if (it == asset.metadata.end()) {
    return false;
  }
  std::string value = it->second;
  std::transform(value.begin(), value.end(), value.begin(),
                 [](const unsigned char character) {
                   return static_cast<char>(std::tolower(character));
                 });
  return value == "1" || value == "true" || value == "yes";
}

} // namespace

std::string_view ToString(const DFlashQuantization quantization) {
  switch (quantization) {
  case DFlashQuantization::kFp16:
    return "fp16";
  case DFlashQuantization::kInt8:
    return "int8";
  case DFlashQuantization::kInt4:
    return "int4";
  case DFlashQuantization::kInt2:
    return "int2";
  case DFlashQuantization::kUnknown:
    return "unknown";
  }
  return "unknown";
}

bool ParseDFlashQuantization(const std::string_view value,
                             DFlashQuantization *quantization) {
  if (quantization == nullptr) {
    return false;
  }
  if (value == "fp16" || value == "f16") {
    *quantization = DFlashQuantization::kFp16;
  } else if (value == "int8" || value == "q8") {
    *quantization = DFlashQuantization::kInt8;
  } else if (value == "int4" || value == "q4") {
    *quantization = DFlashQuantization::kInt4;
  } else if (value == "int2" || value == "q2") {
    *quantization = DFlashQuantization::kInt2;
  } else {
    *quantization = DFlashQuantization::kUnknown;
    return false;
  }
  return true;
}

std::optional<DFlashDescriptor> ParseDFlashManifestBody(
    const std::string &manifestBody) {
  DFlashDescriptor descriptor;
  std::istringstream stream(manifestBody);
  std::string line;
  while (std::getline(stream, line)) {
    const std::string trimmed = Trim(line);
    if (trimmed.empty() || trimmed.front() == '#') {
      continue;
    }
    const std::size_t equals = trimmed.find('=');
    if (equals == std::string::npos) {
      continue;
    }
    const std::string key = Trim(trimmed.substr(0, equals));
    const std::string value = Trim(trimmed.substr(equals + 1));
    if (key == "family") {
      descriptor.family = value;
    } else if (key == "target_family") {
      descriptor.targetFamily = value;
    } else if (key == "target_model") {
      descriptor.targetModel = value;
    } else if (key == "tokenizer_hash") {
      descriptor.tokenizerHash = value;
    } else if (key == "file") {
      descriptor.filePath = value;
    } else if (key == "quantization") {
      if (!ParseDFlashQuantization(value, &descriptor.quantization)) {
        return std::nullopt;
      }
    } else if (key == "backend") {
      descriptor.backend = value;
    } else if (key == "max_draft_tokens") {
      if (!ParseSize(value, &descriptor.maxDraftTokens)) {
        return std::nullopt;
      }
    } else if (key == "estimated_memory_gib") {
      if (!ParseSize(value, &descriptor.estimatedMemoryGiB)) {
        return std::nullopt;
      }
    }
  }
  if (descriptor.family.empty() || descriptor.targetModel.empty() ||
      descriptor.tokenizerHash.empty() || descriptor.filePath.empty() ||
      descriptor.quantization == DFlashQuantization::kUnknown ||
      descriptor.maxDraftTokens == 0) {
    return std::nullopt;
  }
  return descriptor;
}

DFlashCapability DiscoverDFlashCapability(const ModelAsset &asset,
                                          const std::string_view backend) {
  DFlashCapability result;
  if (backend.empty()) {
    result.reason = "backend-unknown";
    return result;
  }
  if (!IsTrue(asset, "dflash_supported") &&
      !IsTrue(asset, "capability.speculative.dflash")) {
    result.reason = "dflash-not-explicitly-advertised";
    return result;
  }
  result.supported = true;
  result.evidence = "explicit-model-metadata";
  result.reason = "dflash-capability-proven";
  return result;
}

DFlashCompatibilityResult ValidateDFlashCompatibility(
    const DFlashDescriptor &draft,
    const DFlashCompatibilityRequest &request) {
  DFlashCompatibilityResult result;
  if (draft.targetFamily.empty() || draft.targetFamily != request.targetFamily) {
    result.reason = "target-family-mismatch";
    return result;
  }
  if (draft.targetModel != request.targetModel) {
    result.reason = "target-model-mismatch";
    return result;
  }
  if (draft.tokenizerHash != request.targetTokenizerHash) {
    result.reason = "tokenizer-hash-mismatch";
    return result;
  }
  if (!request.targetBackend.empty() && !draft.backend.empty() &&
      request.targetBackend != draft.backend) {
    result.reason = "backend-mismatch";
    return result;
  }
  if (!request.allowQuantizedDraft &&
      draft.quantization != DFlashQuantization::kFp16) {
    result.reason = "quantized-draft-disabled";
    return result;
  }
  if (draft.estimatedMemoryGiB != 0 && request.availableMemoryGiB != 0 &&
      draft.estimatedMemoryGiB > request.availableMemoryGiB) {
    result.reason = "memory-budget-insufficient";
    return result;
  }
  result.compatible = true;
  result.placement = "target-backend";
  result.reason = "dflash-compatible";
  return result;
}

DFlashTelemetry ComputeDFlashTelemetry(const std::size_t draftAttempts,
                                       const std::size_t acceptedTokens,
                                       const double draftTokensPerSecond,
                                       const double targetTokensPerSecond) {
  DFlashTelemetry result;
  result.draftAttempts = draftAttempts;
  result.acceptedTokens = std::min(acceptedTokens, draftAttempts);
  result.rejectedTokens = draftAttempts - result.acceptedTokens;
  result.acceptanceRate =
      draftAttempts == 0
          ? 0.0
          : static_cast<double>(result.acceptedTokens) /
                static_cast<double>(draftAttempts);
  result.draftTokensPerSecond = draftTokensPerSecond;
  result.targetTokensPerSecond = targetTokensPerSecond;
  return result;
}

} // namespace us4
