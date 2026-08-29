#pragma once

#include <cstddef>
#include <string_view>

namespace us4 {

enum class PackingMode { kDecode, kPrefill, kBatch };

struct TilePolicy {
  PackingMode mode = PackingMode::kDecode;
  std::size_t tileRows = 0;
  std::size_t tileCols = 0;
  std::size_t scratchBytes = 0;
  bool enabled = false;
  bool isolated = true;
  std::string_view reason;
};

TilePolicy SelectTilePolicy(std::size_t rows, std::size_t inner,
                            std::size_t columns, PackingMode mode,
                            std::size_t cacheBudgetBytes,
                            float measuredSpeedup = -1.0F,
                            float p95Regression = 0.0F);

}  // namespace us4
