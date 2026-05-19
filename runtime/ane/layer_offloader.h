#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include "core/hardware_probe.h"
#include "core/runtime_mode.h"
#include "core/tensor.h"

namespace us4 {

enum class OffloadLayerType {
  kEmbedding,
  kAttentionQkv,
  kAttentionOutput,
  kMlpUpProjection,
  kMlpDownProjection,
  kRouter,
};

struct OffloadLayerRequest {
  std::string family;
  std::string layerName;
  OffloadLayerType layerType = OffloadLayerType::kEmbedding;
  RuntimeMode mode = RuntimeMode::kNano;
  std::size_t tokenCount = 0;
  std::size_t hiddenSize = 0;
  DType weightDType = DType::kFloat32;
  bool staticShape = true;
};

struct OffloadDecision {
  bool eligible = false;
  bool fallbackToMetal = true;
  std::string backend = "metal";
  std::string reason = "ane-unavailable";
};

enum class LayerKind {
  kAttention,
  kMlp,
  kStateful,
  kEmbedding,
  kRouter,
};

struct LayerDescriptor {
  std::string name;
  LayerKind kind = LayerKind::kStateful;
  bool staticShape = false;
};

struct LayerOffloadPlan {
  std::vector<std::string> aneLayers;
  std::vector<std::string> metalLayers;
  std::vector<std::string> rejectedLayers;
};

std::string_view ToString(OffloadLayerType layerType);
LayerOffloadPlan PlanLayerOffload(const std::vector<LayerDescriptor> &layers,
                                  bool aneAvailable);

class LayerOffloader {
public:
  LayerOffloader() = default;
  explicit LayerOffloader(const HardwareProbeResult &hardware);

  bool Available() const;
  std::string_view Reason() const;
  OffloadDecision Decide(const OffloadLayerRequest &request) const;

private:
  bool available_ = false;
  std::string reason_ = "ane-unavailable";
};

} // namespace us4
