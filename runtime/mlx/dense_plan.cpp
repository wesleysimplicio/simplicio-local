#include "mlx/dense_plan.h"

namespace us4 {

MlxDensePlan BuildMlxDensePlan(const std::size_t tokenCount,
                               const std::size_t hiddenSize,
                               const std::size_t vocabularySize) {
  MlxDensePlan plan{
      .tokenCount = tokenCount,
      .hiddenSize = hiddenSize,
      .vocabularySize = vocabularySize,
  };

  if (tokenCount == 0 || hiddenSize == 0 || vocabularySize == 0) {
    return plan;
  }

  plan.operations.push_back({
      .kind = MlxOperationKind::kEmbeddingLookup,
      .extent = tokenCount * hiddenSize,
  });
  plan.operations.push_back({
      .kind = MlxOperationKind::kAttention,
      .extent = tokenCount * hiddenSize,
  });
  plan.operations.push_back({
      .kind = MlxOperationKind::kProjection,
      .extent = hiddenSize * vocabularySize,
  });

  return plan;
}

}  // namespace us4
