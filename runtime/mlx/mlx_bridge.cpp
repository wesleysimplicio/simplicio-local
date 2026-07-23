#include "mlx/mlx_bridge.h"

namespace us4 {

MlxBridge::MlxBridge(const HardwareProbeResult& hardware)
    : nativeBackend_(std::make_shared<NativeMlxBackend>()) {
  if (!hardware.hasMlx || !hardware.isAppleSilicon) {
    reason_ = "mlx-unavailable";
    return;
  }
  if (!nativeBackend_->Available()) {
    reason_ = std::string(nativeBackend_->Reason());
    return;
  }
  available_ = true;
  reason_ = "mlx-native-ready";
}

bool MlxBridge::Available() const { return available_; }

std::string_view MlxBridge::Reason() const { return reason_; }

bool MlxBridge::BuildDensePlan(const std::string_view family,
                               const std::size_t tokenCount,
                               const std::shared_ptr<UnifiedAllocation>& allocation) {
  if (!available_ || family.empty() || tokenCount == 0) {
    return false;
  }

  const MlxDensePlan densePlan = BuildMlxDensePlan(tokenCount, 8U, 16U);
  if (densePlan.operations.empty()) {
    return false;
  }

  lastPlan_ = MlxGraphPlan{
      .family = std::string(family),
      .tokenCount = tokenCount,
      .usesUnifiedAllocation = allocation != nullptr && allocation->gpuVisible,
      .operations = densePlan.operations,
  };
  lastEvaluationSucceeded_ = false;
  reason_ = "mlx-plan-built";
  return true;
}

bool MlxBridge::EvaluateLastPlan() {
  if (!available_ || !lastPlan_.has_value()) {
    return false;
  }

  const std::vector<float> lhs = {1.0F, 2.0F, 3.0F, 4.0F};
  const std::vector<float> rhs = {1.0F, 0.0F, 0.0F, 1.0F};
  std::vector<float> output;
  lastEvaluationSucceeded_ = Matmul(lhs, rhs, 2U, 2U, 2U, output);
  if (lastEvaluationSucceeded_) {
    reason_ = "mlx-plan-evaluated";
  }
  return lastEvaluationSucceeded_;
}

bool MlxBridge::Matmul(const std::span<const float> lhs,
                       const std::span<const float> rhs,
                       const std::size_t rows, const std::size_t inner,
                       const std::size_t columns, std::vector<float> &output) {
  if (!available_ || nativeBackend_ == nullptr) {
    reason_ = nativeBackend_ != nullptr ? std::string(nativeBackend_->Reason())
                                        : "mlx-unavailable";
    return false;
  }

  NativeMlxMatmulResult result =
      nativeBackend_->Matmul(lhs, rhs, rows, inner, columns);
  reason_ = result.reason;
  if (!result.succeeded) {
    return false;
  }
  output = std::move(result.values);
  return true;
}

bool MlxBridge::NativeBackendCompiled() const {
  return nativeBackend_ != nullptr && nativeBackend_->Compiled();
}

const std::optional<MlxGraphPlan>& MlxBridge::LastPlan() const { return lastPlan_; }

bool MlxBridge::LastEvaluationSucceeded() const { return lastEvaluationSucceeded_; }

}  // namespace us4
