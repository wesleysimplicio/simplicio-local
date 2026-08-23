#include "speculative/capability.h"

#include <algorithm>
#include <cctype>
#include <string>
#include <utility>

namespace us4 {

namespace {

bool IsTrue(const ModelAsset &asset, const std::string_view key) {
  const auto it = asset.metadata.find(std::string(key));
  if (it == asset.metadata.end()) {
    return false;
  }
  std::string value = it->second;
  std::transform(value.begin(), value.end(), value.begin(),
                 [](const unsigned char c) {
                   return static_cast<char>(std::tolower(c));
                 });
  return value == "1" || value == "true" || value == "yes";
}

bool HasMetadata(const ModelAsset &asset, const std::string_view key) {
  return asset.metadata.find(std::string(key)) != asset.metadata.end();
}

SpeculativeCapability Capability(const SpeculativeStrategy strategy,
                                 const bool supported,
                                 std::string evidence,
                                 std::string reason) {
  return SpeculativeCapability{strategy, supported, std::move(evidence),
                               std::move(reason)};
}

const SpeculativeCapability *FindCapability(
    const SpeculativeCapabilitySnapshot &snapshot,
    const SpeculativeStrategy strategy) {
  for (const auto &capability : snapshot.capabilities) {
    if (capability.strategy == strategy) {
      return &capability;
    }
  }
  return nullptr;
}

} // namespace

std::string_view ToString(const SpeculativeStrategy strategy) {
  switch (strategy) {
  case SpeculativeStrategy::kBaseline:
    return "baseline";
  case SpeculativeStrategy::kNgramPromptLookup:
    return "ngram_prompt_lookup";
  case SpeculativeStrategy::kDraftModel:
    return "draft_model";
  case SpeculativeStrategy::kDFlash:
    return "dflash";
  case SpeculativeStrategy::kMtp:
    return "mtp";
  }
  return "unknown";
}

bool ParseSpeculativeStrategy(const std::string_view value,
                              SpeculativeStrategy *strategy) {
  if (strategy == nullptr) {
    return false;
  }
  if (value == "baseline" || value == "off") {
    *strategy = SpeculativeStrategy::kBaseline;
  } else if (value == "ngram" || value == "prompt_lookup" ||
             value == "ngram_prompt_lookup") {
    *strategy = SpeculativeStrategy::kNgramPromptLookup;
  } else if (value == "draft" || value == "draft_model") {
    *strategy = SpeculativeStrategy::kDraftModel;
  } else if (value == "dflash") {
    *strategy = SpeculativeStrategy::kDFlash;
  } else if (value == "mtp" || value == "self_speculative") {
    *strategy = SpeculativeStrategy::kMtp;
  } else {
    return false;
  }
  return true;
}

SpeculativeCapabilitySnapshot DiscoverSpeculativeCapabilities(
    const ModelAsset &asset, const HardwareProbeResult &hardware,
    const std::string_view backend, const std::string_view backendVersion) {
  SpeculativeCapabilitySnapshot snapshot;
  snapshot.modelFamily = asset.family;
  snapshot.modelName = asset.modelName;
  snapshot.backend = std::string(backend);
  snapshot.backendVersion = std::string(backendVersion);
  snapshot.platform = hardware.platform;
  snapshot.architecture = hardware.architecture;
  snapshot.cpuAvailable = !hardware.architecture.empty();
  snapshot.metalAvailable = hardware.hasMetal;
  snapshot.cudaAvailable = hardware.hasCuda;
  snapshot.availableMemoryGiB = hardware.availableMemoryGiB != 0
                                    ? hardware.availableMemoryGiB
                                    : hardware.unifiedMemoryGiB;
  snapshot.gpuMemoryGiB = std::max(hardware.gpuMemoryGiB,
                                   hardware.cudaMemoryGiB);

  snapshot.capabilities.push_back(Capability(
      SpeculativeStrategy::kBaseline, true, "local-baseline",
      "baseline decoding is always available"));

  const bool explicitNgram =
      IsTrue(asset, "capability.speculative.ngram_prompt_lookup") ||
      IsTrue(asset, "llama.speculative.ngram");
  snapshot.capabilities.push_back(Capability(
      SpeculativeStrategy::kNgramPromptLookup, explicitNgram,
      explicitNgram ? "model-metadata" : "none",
      explicitNgram ? "backend explicitly advertises n-gram/prompt lookup"
                    : "backend/model did not advertise n-gram support"));

  const bool hasDraft = !asset.draftModelPath.empty() && asset.sharedTokenizer;
  snapshot.capabilities.push_back(Capability(
      SpeculativeStrategy::kDraftModel, hasDraft,
      hasDraft ? "draft-path+shared-tokenizer" : "none",
      hasDraft ? "draft artifact and shared tokenizer are present"
               : "draft artifact or shared tokenizer is unavailable"));

  const bool explicitDFlash =
      IsTrue(asset, "capability.speculative.dflash") ||
      IsTrue(asset, "dflash_supported");
  snapshot.capabilities.push_back(Capability(
      SpeculativeStrategy::kDFlash, explicitDFlash,
      explicitDFlash ? "model-metadata" : "none",
      explicitDFlash ? "model metadata explicitly validates DFlash"
                     : "DFlash support is not explicitly proven"));

  const bool explicitMtp = IsTrue(asset, "capability.speculative.mtp") ||
                           IsTrue(asset, "mtp_supported") ||
                           HasMetadata(asset, "mtp_depth");
  snapshot.capabilities.push_back(Capability(
      SpeculativeStrategy::kMtp, explicitMtp,
      explicitMtp ? "model-metadata" : "none",
      explicitMtp ? "model metadata explicitly exposes MTP"
                  : "MTP support is not explicitly proven"));
  return snapshot;
}

SpeculativeExecutionPlan MakeSpeculativeExecutionPlan(
    const SpeculativeCapabilitySnapshot &snapshot,
    const SpeculativeExecutionRequest &request) {
  SpeculativeExecutionPlan plan;
  plan.maxDraftTokens = std::max<std::size_t>(1U, request.maxDraftTokens);
  if (request.requested == SpeculativeStrategy::kBaseline) {
    plan.reason = "baseline-requested";
    return plan;
  }

  const SpeculativeCapability *capability =
      FindCapability(snapshot, request.requested);
  if (capability != nullptr && capability->supported) {
    plan.selected = request.requested;
    plan.usesSpeculation = true;
    plan.reason = "capability-proven:" + capability->evidence;
    return plan;
  }

  const std::string detail = capability == nullptr
                                 ? "capability-not-advertised"
                                 : capability->reason;
  if (request.allowFallback) {
    plan.usedFallback = true;
    plan.reason = "fallback-baseline:" + detail;
    return plan;
  }
  plan.selected = request.requested;
  plan.reason = "unsupported-no-fallback:" + detail;
  return plan;
}

} // namespace us4
