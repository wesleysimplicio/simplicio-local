#pragma once

#include <cstddef>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "core/hardware_probe.h"
#include "memory/unified_allocator.h"
#include "mlx/dense_plan.h"
#include "mlx/native_mlx_backend.h"

namespace us4 {

struct MlxGraphPlan {
  std::string family;
  std::size_t tokenCount = 0;
  bool usesUnifiedAllocation = false;
  std::vector<MlxDenseOperation> operations;
};

class MlxBridge {
 public:
  MlxBridge() = default;
  explicit MlxBridge(const HardwareProbeResult& hardware);

  bool Available() const;
  std::string_view Reason() const;
  bool BuildDensePlan(std::string_view family,
                      std::size_t tokenCount,
                      const std::shared_ptr<UnifiedAllocation>& allocation = nullptr);
  bool EvaluateLastPlan();
  bool Matmul(std::span<const float> lhs, std::span<const float> rhs,
              std::size_t rows, std::size_t inner, std::size_t columns,
              std::vector<float> &output);
  bool NativeBackendCompiled() const;
  const std::optional<MlxGraphPlan>& LastPlan() const;
  bool LastEvaluationSucceeded() const;

 private:
  bool available_ = false;
  bool lastEvaluationSucceeded_ = false;
  std::string reason_ = "mlx-unavailable";
  std::optional<MlxGraphPlan> lastPlan_;
  std::shared_ptr<NativeMlxBackend> nativeBackend_;
};

}  // namespace us4
