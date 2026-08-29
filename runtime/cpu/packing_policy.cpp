#include "cpu/packing_policy.h"

#include <algorithm>

namespace us4 {

namespace {

constexpr float kPromotionSpeedup = 0.02F;
constexpr float kMaxP95Regression = 0.10F;

}  // namespace

TilePolicy SelectTilePolicy(const std::size_t rows, const std::size_t inner,
                            const std::size_t columns, const PackingMode mode,
                            const std::size_t cacheBudgetBytes,
                            const float measuredSpeedup,
                            const float p95Regression) {
  TilePolicy policy;
  policy.mode = mode;
  policy.isolated = true;
  if (rows == 0U || inner == 0U || columns == 0U || cacheBudgetBytes == 0U) {
    policy.reason = "invalid-or-empty-shape";
    return policy;
  }
  const std::size_t rowHint = mode == PackingMode::kDecode
                                  ? 1U
                                  : (mode == PackingMode::kPrefill ? 32U : 8U);
  const std::size_t columnHint = mode == PackingMode::kBatch
                                     ? 64U
                                     : 128U;
  policy.tileRows = std::min(rows, rowHint);
  policy.tileCols = std::min(columns, columnHint);
  while (policy.tileRows * inner + inner * policy.tileCols > cacheBudgetBytes &&
         (policy.tileRows > 1U || policy.tileCols > 1U)) {
    if (policy.tileCols >= policy.tileRows && policy.tileCols > 1U) {
      policy.tileCols = std::max<std::size_t>(1U, policy.tileCols / 2U);
    } else {
      policy.tileRows = std::max<std::size_t>(1U, policy.tileRows / 2U);
    }
  }
  policy.scratchBytes = policy.tileRows * inner + inner * policy.tileCols;
  const bool evidenceOk = measuredSpeedup > kPromotionSpeedup;
  const bool regressionOk = p95Regression >= 0.0F &&
                            p95Regression <= kMaxP95Regression;
  policy.enabled = evidenceOk && regressionOk &&
                   policy.scratchBytes <= cacheBudgetBytes;
  if (policy.enabled) {
    policy.reason = "tiling-enabled-by-bounded-non-regressive-evidence";
  } else if (!regressionOk) {
    policy.reason = "p95-regression-auto-disabled";
  } else if (measuredSpeedup < 0.0F) {
    policy.reason = "no-measurement-auto-disabled";
  } else if (!evidenceOk) {
    policy.reason = "measurement-below-promotion-threshold";
  } else {
    policy.reason = "cache-budget-exceeded-auto-disabled";
  }
  return policy;
}

}  // namespace us4
