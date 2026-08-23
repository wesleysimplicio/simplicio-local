#include "speculative/mtp_speculative.h"

#include <algorithm>
#include <charconv>
#include <cctype>
#include <sstream>

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

bool HasMtpTensor(const ModelAsset &asset) {
  for (const auto &[name, shape] : asset.realTensorShapes) {
    (void)shape;
    if (name.find("mtp") != std::string::npos ||
        name.find("multi_token") != std::string::npos) {
      return true;
    }
  }
  return false;
}

} // namespace

std::optional<MtpDescriptor> ParseMtpManifestBody(
    const std::string &manifestBody) {
  MtpDescriptor descriptor;
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
    } else if (key == "model_id") {
      descriptor.modelId = value;
    } else if (key == "tokenizer_hash") {
      descriptor.tokenizerHash = value;
    } else if (key == "backend") {
      descriptor.backend = value;
    } else if (key == "head_tensor") {
      descriptor.headTensor = value;
    } else if (key == "depth" && !ParseSize(value, &descriptor.depth)) {
      return std::nullopt;
    }
  }
  if (descriptor.family.empty() || descriptor.modelId.empty() ||
      descriptor.tokenizerHash.empty() || descriptor.backend.empty() ||
      descriptor.headTensor.empty() || descriptor.depth == 0) {
    return std::nullopt;
  }
  return descriptor;
}

MtpCapability DetectMtpCapability(const ModelAsset &asset,
                                  const std::string_view backend) {
  MtpCapability result;
  if (backend.empty()) {
    result.reason = "backend-unknown";
    return result;
  }
  const auto depthIt = asset.metadata.find("mtp_depth");
  if (!IsTrue(asset, "mtp_supported") && depthIt == asset.metadata.end() &&
      !HasMtpTensor(asset)) {
    result.reason = "mtp-not-explicitly-proven";
    return result;
  }
  if (depthIt != asset.metadata.end()) {
    if (!ParseSize(depthIt->second, &result.depth) || result.depth == 0) {
      result.reason = "invalid-mtp-depth";
      return result;
    }
    result.evidence = "mtp_depth-metadata";
  } else {
    result.depth = 1;
    result.evidence = HasMtpTensor(asset) ? "mtp-tensor-record" : "mtp-supported-metadata";
  }
  result.supported = true;
  result.reason = "mtp-capability-proven";
  return result;
}

MtpCompatibilityResult ValidateMtpCompatibility(
    const MtpDescriptor &descriptor,
    const MtpCompatibilityRequest &request) {
  MtpCompatibilityResult result;
  if (descriptor.family != request.targetFamily) {
    result.reason = "model-family-mismatch";
  } else if (descriptor.modelId != request.targetModel) {
    result.reason = "model-id-mismatch";
  } else if (descriptor.tokenizerHash != request.targetTokenizerHash) {
    result.reason = "tokenizer-hash-mismatch";
  } else if (descriptor.backend != request.targetBackend) {
    result.reason = "backend-mismatch";
  } else {
    result.compatible = true;
    result.reason = "mtp-compatible";
  }
  return result;
}

MtpExecutionPlan MakeMtpExecutionPlan(const MtpCapability &capability,
                                      const std::size_t requestedDraftTokens) {
  MtpExecutionPlan plan;
  plan.maxDraftTokens = std::max<std::size_t>(1U, requestedDraftTokens);
  if (!capability.supported || capability.depth == 0) {
    plan.reason = "fallback-baseline:" + capability.reason;
    return plan;
  }
  plan.enabled = true;
  plan.depth = capability.depth;
  plan.maxDraftTokens = std::min(plan.maxDraftTokens, capability.depth);
  plan.reason = "mtp-enabled:" + capability.evidence;
  return plan;
}

MtpTelemetry ComputeMtpTelemetry(const std::size_t proposedTokens,
                                 const std::size_t acceptedTokens) {
  MtpTelemetry result;
  result.proposedTokens = proposedTokens;
  result.acceptedTokens = std::min(proposedTokens, acceptedTokens);
  result.rejectedTokens = proposedTokens - result.acceptedTokens;
  result.acceptanceRate =
      proposedTokens == 0
          ? 0.0
          : static_cast<double>(result.acceptedTokens) /
                static_cast<double>(proposedTokens);
  return result;
}

} // namespace us4
