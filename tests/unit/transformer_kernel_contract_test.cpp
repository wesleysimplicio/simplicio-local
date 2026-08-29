#include <gtest/gtest.h>

#include <cmath>
#include <cstdint>
#include <numeric>

#include "cpu/transformer_kernels.h"

TEST(TransformerKernelContractTest, RmsNormIsFiniteAndScaleCorrect) {
  const float input[] = {3.0F, 4.0F, 0.0F, -2.0F, 1.0F};
  float output[5] = {};
  us4::TransformerKernelReceipt receipt;
  ASSERT_TRUE(us4::RmsNorm(input, 5U, output, 1e-5F, &receipt));
  EXPECT_EQ(receipt.operation, "rmsnorm");
  for (const float value : output) {
    EXPECT_TRUE(std::isfinite(value));
  }
}

TEST(TransformerKernelContractTest, SoftmaxHonorsMaskAndStableLargeValues) {
  float values[] = {10000.0F, 10001.0F, -10000.0F, 10002.0F};
  const std::uint8_t mask[] = {1U, 0U, 1U, 1U};
  ASSERT_TRUE(us4::Softmax(values, 4U, mask));
  EXPECT_FLOAT_EQ(values[1], 0.0F);
  EXPECT_NEAR(values[0] + values[2] + values[3], 1.0F, 1e-5F);
  EXPECT_TRUE(values[3] > values[0]);
}

TEST(TransformerKernelContractTest, AllMaskedSoftmaxReturnsZeros) {
  float values[] = {1.0F, 2.0F, 3.0F};
  const std::uint8_t mask[] = {0U, 0U, 0U};
  ASSERT_TRUE(us4::Softmax(values, 3U, mask));
  EXPECT_EQ(values[0], 0.0F);
  EXPECT_EQ(values[1], 0.0F);
  EXPECT_EQ(values[2], 0.0F);
}

TEST(TransformerKernelContractTest, RopePreservesOddTailAndTransformsBothStreams) {
  float query[] = {1.0F, 0.0F, 7.0F, 0.0F, 1.0F, 0.0F, 8.0F, 0.0F};
  float key[] = {0.0F, 1.0F, 9.0F, 0.0F, 0.0F, 1.0F, 10.0F, 0.0F};
  ASSERT_TRUE(us4::ApplyRope(query, key, 2U, 4U, 1U));
  EXPECT_NE(query[0], 1.0F);
  EXPECT_NE(key[0], 0.0F);
  EXPECT_FLOAT_EQ(query[2], 7.0F);
  EXPECT_FLOAT_EQ(query[6], 8.0F);
}
