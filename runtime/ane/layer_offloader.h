#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace us4 {

// LayerOffloader picks which layers go to the ANE based on a small
// allow-list of layer types. Attention and MLP layers without time-varying
// state are good candidates; layers tied to KV cache state must stay on
// Metal.

enum class LayerKind {
  kAttention,
  kMlp,
  kEmbedding,
  kProjection,
  kStateful,
};

struct LayerDescriptor {
  std::string name;
  LayerKind kind = LayerKind::kStateful;
  bool isStatic = false;
};

struct LayerOffloadPlan {
  std::vector<std::string> aneLayers;
  std::vector<std::string> metalLayers;
  std::vector<std::string> rejectedLayers;
};

LayerOffloadPlan PlanLayerOffload(const std::vector<LayerDescriptor>& layers,
                                  bool aneAvailable);

}  // namespace us4
