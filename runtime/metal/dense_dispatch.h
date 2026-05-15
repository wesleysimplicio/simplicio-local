#pragma once

#include <cstddef>
#include <memory>
#include <vector>

#include "metal/command_queue.h"

namespace us4 {

struct DenseMetalDispatchStep {
  MetalKernelKind kernel = MetalKernelKind::kMatmul;
  std::size_t threadgroups = 0;
  std::size_t threadsPerGroup = 0;
};

struct DenseMetalDispatchPlan {
  std::size_t tokenCount = 0;
  std::size_t hiddenSize = 0;
  std::size_t vocabularySize = 0;
  std::vector<DenseMetalDispatchStep> steps;
};

DenseMetalDispatchPlan BuildDenseMetalDispatchPlan(std::size_t tokenCount,
                                                   std::size_t hiddenSize,
                                                   std::size_t vocabularySize);
bool ExecuteDenseMetalDispatchPlan(MetalCommandQueue& queue,
                                   const DenseMetalDispatchPlan& plan,
                                   const std::shared_ptr<UnifiedAllocation>& allocation);

}  // namespace us4
