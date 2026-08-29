#include <gtest/gtest.h>

#include "benchmarks/simd_release_gate.h"

TEST(SimdReleaseGateContractTest, RequiresAllPromotionGates) {
  const us4::benchmarks::SimdGateObservation passing{
      true, true, false, true, true, true, 10.0F, 11.0F, 7.0F, 11.5F};
  const auto result = us4::benchmarks::EvaluateSimdReleaseGate(passing);
  EXPECT_TRUE(result.accepted);
  EXPECT_EQ(result.reason, "all-correctness-benchmark-model-gates-passed");
}

TEST(SimdReleaseGateContractTest, FailsClosedForMissingModelOrRegressiveP95) {
  auto missingModel = us4::benchmarks::SimdGateObservation{
      true, true, false, true, false, true, 10.0F, 11.0F, 7.0F, 11.0F};
  EXPECT_FALSE(us4::benchmarks::EvaluateSimdReleaseGate(missingModel).accepted);
  EXPECT_EQ(us4::benchmarks::EvaluateSimdReleaseGate(missingModel).reason,
            "end-to-end-model-evidence-missing");

  missingModel.endToEndModel = true;
  missingModel.candidateP95Ms = 20.0F;
  const auto regressive = us4::benchmarks::EvaluateSimdReleaseGate(missingModel);
  EXPECT_FALSE(regressive.accepted);
  EXPECT_EQ(regressive.reason, "p95-regression-exceeds-budget");
}
