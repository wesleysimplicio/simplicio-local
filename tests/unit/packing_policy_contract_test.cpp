#include <gtest/gtest.h>

#include "cpu/packing_policy.h"

TEST(PackingPolicyContractTest, RequiresMeasuredNonRegressiveEvidence) {
  const auto noEvidence = us4::SelectTilePolicy(
      32U, 128U, 128U, us4::PackingMode::kPrefill, 32U * 1024U);
  EXPECT_FALSE(noEvidence.enabled);
  EXPECT_EQ(noEvidence.reason, "no-measurement-auto-disabled");

  const auto regressive = us4::SelectTilePolicy(
      32U, 128U, 128U, us4::PackingMode::kPrefill, 32U * 1024U, 0.2F,
      0.2F);
  EXPECT_FALSE(regressive.enabled);
  EXPECT_EQ(regressive.reason, "p95-regression-auto-disabled");
}

TEST(PackingPolicyContractTest, SelectsBoundedModeSpecificTiles) {
  const auto decode = us4::SelectTilePolicy(
      16U, 128U, 256U, us4::PackingMode::kDecode, 32U * 1024U, 0.1F,
      0.05F);
  const auto prefill = us4::SelectTilePolicy(
      128U, 128U, 256U, us4::PackingMode::kPrefill, 32U * 1024U, 0.1F,
      0.05F);
  EXPECT_TRUE(decode.enabled);
  EXPECT_TRUE(prefill.enabled);
  EXPECT_EQ(decode.tileRows, 1U);
  EXPECT_LE(prefill.scratchBytes, 32U * 1024U);
  EXPECT_TRUE(decode.isolated);
  EXPECT_TRUE(prefill.isolated);
}
