#include <gtest/gtest.h>

#include <cmath>

#include "core/tensor.h"
#include "cpu/float_kernels.h"

TEST(FloatKernelContractTest, SelectionKeepsPortableFallback) {
  EXPECT_EQ(us4::SelectFloatKernel(false, false).kind,
            us4::FloatKernelKind::kScalar);
  EXPECT_EQ(us4::SelectFloatKernel(true, false).kind,
            us4::FloatKernelKind::kAvx2);
  EXPECT_EQ(us4::SelectFloatKernel(false, true).kind,
            us4::FloatKernelKind::kNeon);
}

TEST(FloatKernelContractTest, Float32MatmulMatchesReferenceWithTail) {
  us4::Tensor lhs({2, 3}, us4::DType::kFloat32);
  us4::Tensor rhs({3, 5}, us4::DType::kFloat32);
  us4::Tensor output({2, 5}, us4::DType::kFloat32);
  for (std::size_t index = 0; index < lhs.ElementCount(); ++index) {
    lhs.MutableDataAsFloat32()[index] = static_cast<float>(index + 1U) / 7.0F;
  }
  for (std::size_t index = 0; index < rhs.ElementCount(); ++index) {
    rhs.MutableDataAsFloat32()[index] =
        static_cast<float>(static_cast<int>(index % 9U) - 4) / 5.0F;
  }
  us4::FloatKernelDispatch dispatch;
  ASSERT_TRUE(us4::CpuFloatMatmul(lhs, rhs, output, &dispatch));
  EXPECT_FALSE(dispatch.reason.empty());
  for (std::size_t row = 0; row < 2U; ++row) {
    for (std::size_t column = 0; column < 5U; ++column) {
      float expected = 0.0F;
      for (std::size_t index = 0; index < 3U; ++index) {
        expected += lhs.DataAsFloat32()[row * 3U + index] *
                    rhs.DataAsFloat32()[index * 5U + column];
      }
      EXPECT_NEAR(output.DataAsFloat32()[row * 5U + column], expected, 1e-6F);
    }
  }
}

TEST(FloatKernelContractTest, Fp16AndBf16UseTheSameReferenceSemantics) {
  for (const auto dtype : {us4::DType::kFloat16, us4::DType::kBFloat16}) {
    us4::Tensor lhs({1, 2}, dtype);
    us4::Tensor rhs({2, 1}, dtype);
    us4::Tensor output({1, 1}, us4::DType::kFloat32);
    lhs.MutableDataAsUInt16()[0] = dtype == us4::DType::kFloat16
                                       ? us4::EncodeFloat16(1.5F)
                                       : us4::EncodeBFloat16(1.5F);
    lhs.MutableDataAsUInt16()[1] = dtype == us4::DType::kFloat16
                                       ? us4::EncodeFloat16(-2.0F)
                                       : us4::EncodeBFloat16(-2.0F);
    rhs.MutableDataAsUInt16()[0] = dtype == us4::DType::kFloat16
                                       ? us4::EncodeFloat16(2.0F)
                                       : us4::EncodeBFloat16(2.0F);
    rhs.MutableDataAsUInt16()[1] = dtype == us4::DType::kFloat16
                                       ? us4::EncodeFloat16(0.5F)
                                       : us4::EncodeBFloat16(0.5F);
    ASSERT_TRUE(us4::CpuFloatMatmul(lhs, rhs, output));
    EXPECT_NEAR(output.DataAsFloat32()[0], 2.0F, 0.02F);
  }
}
