#include "metal/dense_dispatch.h"

#include <algorithm>

namespace us4 {

DenseMetalDispatchPlan BuildDenseMetalDispatchPlan(const std::size_t tokenCount,
                                                   const std::size_t hiddenSize,
                                                   const std::size_t vocabularySize) {
  DenseMetalDispatchPlan plan{
      .tokenCount = tokenCount,
      .hiddenSize = hiddenSize,
      .vocabularySize = vocabularySize,
  };

  if (tokenCount == 0 || hiddenSize == 0 || vocabularySize == 0) {
    return plan;
  }

  const std::size_t sequenceGroups = std::max<std::size_t>(1, tokenCount);
  const std::size_t hiddenGroups = std::max<std::size_t>(1, (hiddenSize + 31U) / 32U);
  const std::size_t vocabGroups = std::max<std::size_t>(1, (vocabularySize + 63U) / 64U);

  plan.steps.push_back({
      .kernel = MetalKernelKind::kMatmul,
      .threadgroups = sequenceGroups * hiddenGroups,
      .threadsPerGroup = 32,
  });
  plan.steps.push_back({
      .kernel = MetalKernelKind::kSoftmax,
      .threadgroups = sequenceGroups * vocabGroups,
      .threadsPerGroup = 64,
  });
  plan.steps.push_back({
      .kernel = MetalKernelKind::kRmsNorm,
      .threadgroups = sequenceGroups * hiddenGroups,
      .threadsPerGroup = 64,
  });

  return plan;
}

bool ExecuteDenseMetalDispatchPlan(MetalCommandQueue& queue,
                                   const DenseMetalDispatchPlan& plan,
                                   const std::shared_ptr<UnifiedAllocation>& allocation) {
  if (!queue.Available() || plan.steps.empty()) {
    return false;
  }

  for (const auto& step : plan.steps) {
    if (!queue.Dispatch(step.kernel, step.threadgroups, step.threadsPerGroup, allocation)) {
      return false;
    }
  }

  return true;
}

}  // namespace us4
