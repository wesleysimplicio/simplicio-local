#include "ane/layer_offloader.h"

namespace us4 {

namespace {

bool SupportsLowBitWeights(const DType dtype) {
  return dtype == DType::kInt4 || dtype == DType::kInt8;
}

} // namespace

std::string_view ToString(const OffloadLayerType layerType) {
  switch (layerType) {
  case OffloadLayerType::kEmbedding:
    return "embedding";
  case OffloadLayerType::kAttentionQkv:
    return "attention-qkv";
  case OffloadLayerType::kAttentionOutput:
    return "attention-output";
  case OffloadLayerType::kMlpUpProjection:
    return "mlp-up";
  case OffloadLayerType::kMlpDownProjection:
    return "mlp-down";
  case OffloadLayerType::kRouter:
    return "router";
  }
  return "embedding";
}

LayerOffloadPlan PlanLayerOffload(const std::vector<LayerDescriptor> &layers,
                                  const bool aneAvailable) {
  LayerOffloadPlan plan;
  for (const LayerDescriptor &layer : layers) {
    const bool aneCandidate =
        layer.staticShape &&
        (layer.kind == LayerKind::kAttention || layer.kind == LayerKind::kMlp);
    if (aneAvailable && aneCandidate) {
      plan.aneLayers.push_back(layer.name);
    } else if (layer.kind == LayerKind::kStateful) {
      plan.rejectedLayers.push_back(layer.name);
    } else {
      plan.metalLayers.push_back(layer.name);
    }
  }
  return plan;
}

LayerOffloader::LayerOffloader(const HardwareProbeResult &hardware)
    : available_(hardware.hasAne && hardware.supportsCoreMl) {
  if (!available_) {
    reason_ = "ane-unavailable";
    return;
  }

  reason_ = "ane-layer-offloader-ready";
}

bool LayerOffloader::Available() const { return available_; }

std::string_view LayerOffloader::Reason() const { return reason_; }

OffloadDecision
LayerOffloader::Decide(const OffloadLayerRequest &request) const {
  if (!available_) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-unavailable"};
  }
  if (request.mode != RuntimeMode::kFull) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-full-mode-only"};
  }
  if (request.family.empty() || request.layerName.empty()) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-layer-metadata-missing"};
  }
  if (!request.staticShape) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-static-shape-required"};
  }
  if (request.tokenCount == 0 || request.hiddenSize == 0) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-invalid-shape"};
  }
  if (request.tokenCount > 64 || request.hiddenSize % 8U != 0U) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-shape-out-of-range"};
  }
  if (SupportsLowBitWeights(request.weightDType)) {
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-lowbit-fallback"};
  }

  switch (request.layerType) {
  case OffloadLayerType::kAttentionQkv:
  case OffloadLayerType::kAttentionOutput:
  case OffloadLayerType::kMlpUpProjection:
  case OffloadLayerType::kMlpDownProjection:
    return {.eligible = true,
            .fallbackToMetal = false,
            .backend = "ane",
            .reason = "ane-layer-eligible"};
  case OffloadLayerType::kEmbedding:
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-embedding-metal"};
  case OffloadLayerType::kRouter:
    return {.eligible = false,
            .fallbackToMetal = true,
            .backend = "metal",
            .reason = "ane-router-cpu"};
  }

  return {.eligible = false,
          .fallbackToMetal = true,
          .backend = "metal",
          .reason = "ane-unavailable"};
}

} // namespace us4
