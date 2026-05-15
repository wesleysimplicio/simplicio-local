#pragma once

#include <cstddef>
#include <vector>

namespace us4 {

enum class MlxOperationKind {
  kEmbeddingLookup,
  kAttention,
  kProjection,
};

struct MlxDenseOperation {
  MlxOperationKind kind = MlxOperationKind::kEmbeddingLookup;
  std::size_t extent = 0;
};

struct MlxDensePlan {
  std::size_t tokenCount = 0;
  std::size_t hiddenSize = 0;
  std::size_t vocabularySize = 0;
  std::vector<MlxDenseOperation> operations;
};

MlxDensePlan BuildMlxDensePlan(std::size_t tokenCount, std::size_t hiddenSize, std::size_t vocabularySize);

}  // namespace us4
