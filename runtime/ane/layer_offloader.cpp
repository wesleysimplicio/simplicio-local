#include "ane/layer_offloader.h"

namespace us4 {

LayerOffloadPlan
PlanLayerOffload(const std::vector<LayerDescriptor> &layers,
                 const bool aneAvailable) {
  LayerOffloadPlan plan;
  if (!aneAvailable) {
    for (const auto &layer : layers) {
      plan.metalLayers.push_back(layer.name);
    }
    return plan;
  }
  for (const auto &layer : layers) {
    const bool eligible = layer.isStatic && (layer.kind == LayerKind::kAttention ||
                                              layer.kind == LayerKind::kMlp ||
                                              layer.kind == LayerKind::kProjection);
    if (!eligible) {
      plan.metalLayers.push_back(layer.name);
      if (layer.kind == LayerKind::kStateful) {
        plan.rejectedLayers.push_back(layer.name);
      }
      continue;
    }
    plan.aneLayers.push_back(layer.name);
  }
  return plan;
}

} // namespace us4
