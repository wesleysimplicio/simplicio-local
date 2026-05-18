#pragma once

#include <cstddef>
#include <string>
#include <string_view>

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

std::string_view ToString(OffloadLayerType layerType);

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
