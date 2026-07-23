#include <gtest/gtest.h>

#include "core/hardware_probe.h"
#include "memory/unified_allocator.h"
#include "mlx/dense_plan.h"
#include "mlx/mlx_bridge.h"

namespace {

us4::HardwareProbeResult MlxCapableProbe() {
  us4::HardwareProbeResult probe;
  probe.platform = "macos";
  probe.architecture = "arm64";
  probe.isAppleSilicon = true;
  probe.hasMlx = true;
  return probe;
}

} // namespace

TEST(MlxBridgeContractTest, AvailableBridgeBuildsAndEvaluatesPlan) {
  us4::MlxBridge bridge(MlxCapableProbe());

  if (!bridge.Available()) {
    EXPECT_FALSE(bridge.NativeBackendCompiled());
    EXPECT_EQ(bridge.Reason(), "mlx-not-built-for-host");
    EXPECT_FALSE(bridge.BuildDensePlan("qwen", 12U));
    return;
  }
  EXPECT_TRUE(bridge.NativeBackendCompiled());
  EXPECT_EQ(bridge.Reason(), "mlx-native-ready");

  ASSERT_TRUE(bridge.BuildDensePlan("qwen", 12U));
  ASSERT_TRUE(bridge.LastPlan().has_value());
  EXPECT_EQ(bridge.LastPlan()->family, "qwen");
  EXPECT_EQ(bridge.LastPlan()->tokenCount, 12U);
  EXPECT_FALSE(bridge.LastPlan()->operations.empty());
  EXPECT_FALSE(bridge.LastPlan()->usesUnifiedAllocation);

  EXPECT_TRUE(bridge.EvaluateLastPlan());
  EXPECT_TRUE(bridge.LastEvaluationSucceeded());
  EXPECT_EQ(bridge.Reason(), "mlx-plan-evaluated");
}

TEST(MlxBridgeContractTest, GpuVisibleAllocationMarksUnifiedUse) {
  us4::MlxBridge bridge(MlxCapableProbe());
  if (!bridge.Available()) {
    EXPECT_FALSE(bridge.BuildDensePlan("llama", 8U));
    return;
  }
  us4::UnifiedAllocator allocator;
  const auto shared = allocator.Allocate(256U, true);

  ASSERT_TRUE(bridge.BuildDensePlan("llama", 8U, shared));
  ASSERT_TRUE(bridge.LastPlan().has_value());
  EXPECT_TRUE(bridge.LastPlan()->usesUnifiedAllocation);
}

TEST(MlxBridgeContractTest, UnavailableBridgeRefusesPlans) {
  us4::HardwareProbeResult probe;
  probe.hasMlx = false;
  us4::MlxBridge bridge(probe);

  EXPECT_FALSE(bridge.Available());
  EXPECT_EQ(bridge.Reason(), "mlx-unavailable");
  EXPECT_FALSE(bridge.BuildDensePlan("qwen", 4U));
  EXPECT_FALSE(bridge.EvaluateLastPlan());
  EXPECT_FALSE(bridge.LastPlan().has_value());
}

TEST(MlxBridgeContractTest, BuildPlanRejectsDegenerateInputs) {
  us4::MlxBridge bridge(MlxCapableProbe());
  EXPECT_FALSE(bridge.BuildDensePlan("", 4U));
  EXPECT_FALSE(bridge.BuildDensePlan("qwen", 0U));
}

TEST(MlxBridgeContractTest, LinuxFallbackRejectsSyntheticAppleCapability) {
#if defined(__APPLE__)
  GTEST_SKIP() << "Linux fallback contract only";
#else
  us4::MlxBridge bridge(MlxCapableProbe());
  EXPECT_FALSE(bridge.Available());
  EXPECT_FALSE(bridge.NativeBackendCompiled());
  EXPECT_EQ(bridge.Reason(), "mlx-not-built-for-host");
  const std::vector<float> lhs = {1.0F};
  const std::vector<float> rhs = {1.0F};
  std::vector<float> output;
  EXPECT_FALSE(bridge.Matmul(lhs, rhs, 1U, 1U, 1U, output));
  EXPECT_TRUE(output.empty());
#endif
}

TEST(MlxDensePlanContractTest, BuildsThreeStageGraphWithExpectedExtents) {
  const us4::MlxDensePlan plan = us4::BuildMlxDensePlan(4U, 8U, 16U);

  ASSERT_EQ(plan.operations.size(), 3U);
  EXPECT_EQ(plan.operations[0].kind, us4::MlxOperationKind::kEmbeddingLookup);
  EXPECT_EQ(plan.operations[0].extent, 32U);
  EXPECT_EQ(plan.operations[1].kind, us4::MlxOperationKind::kAttention);
  EXPECT_EQ(plan.operations[1].extent, 32U);
  EXPECT_EQ(plan.operations[2].kind, us4::MlxOperationKind::kProjection);
  EXPECT_EQ(plan.operations[2].extent, 128U);
}

TEST(MlxDensePlanContractTest, ZeroDimensionsProduceEmptyPlan) {
  EXPECT_TRUE(us4::BuildMlxDensePlan(0U, 8U, 16U).operations.empty());
  EXPECT_TRUE(us4::BuildMlxDensePlan(4U, 0U, 16U).operations.empty());
  EXPECT_TRUE(us4::BuildMlxDensePlan(4U, 8U, 0U).operations.empty());
}
