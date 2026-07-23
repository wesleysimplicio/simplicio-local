#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <vector>

#include "core/hardware_probe.h"
#include "metal/command_queue.h"
#include "mlx/mlx_bridge.h"

namespace {

us4::HardwareProbeResult AppleBackendProbe() {
  us4::HardwareProbeResult probe;
  probe.platform = "macos";
  probe.architecture = "arm64";
  probe.isAppleSilicon = true;
  probe.hasMetal = true;
  probe.hasMlx = true;
  return probe;
}

std::vector<float> ReferenceMatmul(const std::vector<float> &lhs,
                                   const std::vector<float> &rhs,
                                   const std::size_t rows,
                                   const std::size_t inner,
                                   const std::size_t columns) {
  std::vector<float> output(rows * columns, 0.0F);
  for (std::size_t row = 0; row < rows; ++row) {
    for (std::size_t column = 0; column < columns; ++column) {
      for (std::size_t index = 0; index < inner; ++index) {
        output[row * columns + column] +=
            lhs[row * inner + index] * rhs[index * columns + column];
      }
    }
  }
  return output;
}

void ExpectNear(const std::vector<float> &actual,
                const std::vector<float> &expected, const float tolerance) {
  ASSERT_EQ(actual.size(), expected.size());
  for (std::size_t index = 0; index < actual.size(); ++index) {
    EXPECT_NEAR(actual[index], expected[index], tolerance) << "index=" << index;
  }
}

} // namespace

TEST(NativeAppleBackendParityTest, MetalMatmulMatchesScalarWhenAvailable) {
  us4::MetalCommandQueue queue(AppleBackendProbe());
  const std::vector<float> lhs = {1.0F, -2.0F, 3.0F, 0.5F, 4.0F, -1.0F};
  const std::vector<float> rhs = {2.0F, 1.0F, -1.0F, 3.0F, 0.25F, -2.0F};
  const std::vector<float> expected = ReferenceMatmul(lhs, rhs, 2U, 3U, 2U);
  std::vector<float> actual;

  if (!queue.Available()) {
    EXPECT_FALSE(queue.Matmul(lhs, rhs, 2U, 3U, 2U, actual));
    EXPECT_TRUE(actual.empty());
    EXPECT_EQ(queue.DispatchCount(), 0U);
    return;
  }

  ASSERT_TRUE(queue.Matmul(lhs, rhs, 2U, 3U, 2U, actual));
  ExpectNear(actual, expected, 1.0e-5F);
  ASSERT_EQ(queue.DispatchCount(), 1U);
  EXPECT_TRUE(queue.Dispatches().front().executed);
  EXPECT_EQ(queue.Reason(), "metal-matmul-executed");
}

TEST(NativeAppleBackendParityTest, MlxMatmulMatchesScalarWhenAvailable) {
  us4::MlxBridge bridge(AppleBackendProbe());
  const std::vector<float> lhs = {1.0F, -2.0F, 3.0F, 0.5F, 4.0F, -1.0F};
  const std::vector<float> rhs = {2.0F, 1.0F, -1.0F, 3.0F, 0.25F, -2.0F};
  const std::vector<float> expected = ReferenceMatmul(lhs, rhs, 2U, 3U, 2U);
  std::vector<float> actual;

  if (!bridge.Available()) {
    EXPECT_FALSE(bridge.Matmul(lhs, rhs, 2U, 3U, 2U, actual));
    EXPECT_TRUE(actual.empty());
    return;
  }

  ASSERT_TRUE(bridge.Matmul(lhs, rhs, 2U, 3U, 2U, actual));
  ExpectNear(actual, expected, 1.0e-5F);
  EXPECT_EQ(bridge.Reason(), "mlx-matmul-evaluated");
}

TEST(NativeAppleBackendParityTest, UnboundMetalDispatchIsNeverRecorded) {
  us4::MetalCommandQueue queue(AppleBackendProbe());
  EXPECT_FALSE(
      queue.Dispatch(us4::MetalKernelKind::kMatmul, 1U, 32U, nullptr));
  EXPECT_EQ(queue.DispatchCount(), 0U);
  if (queue.Available()) {
    EXPECT_EQ(queue.Reason(), "metal-dispatch-requires-bound-buffers");
  }
}
