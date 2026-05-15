#include <gtest/gtest.h>

#include "neon/kernel_profile.h"
#include "neon/neon_matmul.h"

namespace {

us4::HardwareProbeResult MakeArmProbe() {
  us4::HardwareProbeResult probe;
  probe.platform = "macos";
  probe.architecture = "arm64";
  probe.chip = "apple-m";
  probe.hasNeon = true;
  return probe;
}

} // namespace

TEST(NeonContractTest, MatmulProfileUsesLaneAwareTilesForArm64) {
  const us4::Tensor lhs({8, 16}, us4::DType::kFloat16, us4::DeviceType::kCpu);
  const us4::Tensor rhs({16, 32}, us4::DType::kFloat16, us4::DeviceType::kCpu);

  const us4::NeonMatmulProfile profile =
      us4::PlanNeonMatmul(MakeArmProbe(), lhs, rhs);

  EXPECT_EQ(profile.flavor, us4::NeonKernelFlavor::kFp16Lane8);
  EXPECT_EQ(profile.tileRows, 8U);
  EXPECT_EQ(profile.tileCols, 8U);
  EXPECT_EQ(profile.vectorLanes, 8U);
  EXPECT_FALSE(profile.usesAccelerateFallback);
}

TEST(NeonContractTest, Int8MatmulProfilePrefersDotProductPath) {
  const us4::Tensor lhs({8, 32}, us4::DType::kInt8, us4::DeviceType::kCpu);
  const us4::Tensor rhs({32, 32}, us4::DType::kInt8, us4::DeviceType::kCpu);

  const us4::NeonMatmulProfile profile =
      us4::PlanNeonMatmul(MakeArmProbe(), lhs, rhs);

  EXPECT_EQ(profile.flavor, us4::NeonKernelFlavor::kInt8Dot);
  EXPECT_TRUE(profile.usesDotProduct);
  EXPECT_EQ(profile.vectorLanes, 16U);
}

TEST(NeonContractTest, AttentionProfileKeepsFusedSoftmaxContract) {
  const us4::Tensor query({1, 8, 64}, us4::DType::kFloat32,
                          us4::DeviceType::kCpu);
  const us4::Tensor key({1, 8, 64}, us4::DType::kFloat32,
                        us4::DeviceType::kCpu);
  const us4::Tensor value({1, 8, 64}, us4::DType::kFloat32,
                          us4::DeviceType::kCpu);

  const us4::NeonAttentionProfile profile =
      us4::PlanNeonAttention(MakeArmProbe(), query, key, value, true);

  EXPECT_EQ(profile.flavor, us4::NeonKernelFlavor::kFp32Lane4);
  EXPECT_EQ(profile.vectorLanes, 4U);
  EXPECT_EQ(profile.headDimBlock, 32U);
  EXPECT_TRUE(profile.fusesSoftmaxRescale);
  EXPECT_TRUE(profile.supportsCausalMask);
}

TEST(NeonContractTest, NonArmHostsStayOnScalarBridgePlan) {
  us4::HardwareProbeResult probe;
  probe.platform = "windows";
  probe.architecture = "x64";
  probe.hasNeon = false;

  const us4::Tensor lhs({4, 4}, us4::DType::kFloat32, us4::DeviceType::kCpu);
  const us4::Tensor rhs({4, 4}, us4::DType::kFloat32, us4::DeviceType::kCpu);

  const us4::NeonMatmulProfile profile = us4::PlanNeonMatmul(probe, lhs, rhs);

  EXPECT_EQ(profile.flavor, us4::NeonKernelFlavor::kScalarBridge);
  EXPECT_FALSE(profile.usesDotProduct);
}

TEST(NeonContractTest, NeonMatmulMatchesScalarResultForFp32) {
  us4::Tensor lhs({2, 3}, us4::DType::kFloat32, us4::DeviceType::kCpu);
  us4::Tensor rhs({3, 4}, us4::DType::kFloat32, us4::DeviceType::kCpu);
  us4::Tensor output({2, 4}, us4::DType::kFloat32, us4::DeviceType::kCpu);

  float *lhsData = lhs.MutableDataAsFloat32();
  float *rhsData = rhs.MutableDataAsFloat32();
  lhsData[0] = 1.0F;
  lhsData[1] = 2.0F;
  lhsData[2] = 3.0F;
  lhsData[3] = 4.0F;
  lhsData[4] = 5.0F;
  lhsData[5] = 6.0F;

  rhsData[0] = 1.0F;
  rhsData[1] = 0.0F;
  rhsData[2] = 2.0F;
  rhsData[3] = 1.0F;
  rhsData[4] = 0.0F;
  rhsData[5] = 1.0F;
  rhsData[6] = 3.0F;
  rhsData[7] = 0.0F;
  rhsData[8] = 1.0F;
  rhsData[9] = 1.0F;
  rhsData[10] = 0.0F;
  rhsData[11] = 2.0F;

  std::string error;
  ASSERT_TRUE(us4::NeonMatmul(lhs, rhs, output, &error)) << error;

  const float *values = output.DataAsFloat32();
  ASSERT_NE(values, nullptr);
  EXPECT_FLOAT_EQ(values[0], 4.0F);
  EXPECT_FLOAT_EQ(values[1], 5.0F);
  EXPECT_FLOAT_EQ(values[2], 8.0F);
  EXPECT_FLOAT_EQ(values[3], 7.0F);
  EXPECT_FLOAT_EQ(values[4], 10.0F);
  EXPECT_FLOAT_EQ(values[5], 11.0F);
  EXPECT_FLOAT_EQ(values[6], 23.0F);
  EXPECT_FLOAT_EQ(values[7], 16.0F);
}
