#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "core/tensor.h"
#include "cpu/scalar_matmul.h"
#include "neon/neon_matmul.h"

namespace {

us4::Tensor MakeMatrix(std::size_t rows, std::size_t cols,
                       const std::vector<float> &values) {
  us4::Tensor tensor({rows, cols}, us4::DType::kFloat32);
  float *data = tensor.MutableDataAsFloat32();
  for (std::size_t i = 0; i < values.size(); ++i) {
    data[i] = values[i];
  }
  return tensor;
}

} // namespace

TEST(KernelNumericsContractTest, ScalarMatmulMatchesHandComputedReference) {
  // [2x3] * [3x2]:
  //   A = [[1,2,3],[4,5,6]]
  //   B = [[7,8],[9,10],[11,12]]
  //   AB = [[58,64],[139,154]]
  const us4::Tensor lhs = MakeMatrix(2, 3, {1, 2, 3, 4, 5, 6});
  const us4::Tensor rhs = MakeMatrix(3, 2, {7, 8, 9, 10, 11, 12});
  us4::Tensor out({2, 2}, us4::DType::kFloat32);

  std::string error;
  ASSERT_TRUE(us4::ScalarMatmul(lhs, rhs, out, &error)) << error;

  const float *data = out.DataAsFloat32();
  EXPECT_FLOAT_EQ(data[0], 58.0F);
  EXPECT_FLOAT_EQ(data[1], 64.0F);
  EXPECT_FLOAT_EQ(data[2], 139.0F);
  EXPECT_FLOAT_EQ(data[3], 154.0F);
}

TEST(KernelNumericsContractTest, NeonMatmulAgreesWithScalarReference) {
  const std::vector<float> lhsValues = {
      0.5F, -1.0F, 2.0F, 0.25F, 1.5F, -0.5F, 3.0F, 0.75F, -2.0F, 1.0F,
      0.1F, 0.2F,  0.3F, 0.4F,  0.5F, -1.5F, 2.5F, 0.0F,  1.25F, -0.75F,
  };
  const std::vector<float> rhsValues = {
      1.0F, 0.5F,  -0.5F, 2.0F, -1.0F, 0.25F,  0.0F, 1.5F,
      1.0F, -2.0F, 0.75F, 0.5F, 0.5F,  -0.25F, 2.0F,
  };
  const us4::Tensor lhs = MakeMatrix(4, 5, lhsValues);
  const us4::Tensor rhs = MakeMatrix(5, 3, rhsValues);

  us4::Tensor scalarOut({4, 3}, us4::DType::kFloat32);
  us4::Tensor neonOut({4, 3}, us4::DType::kFloat32);
  std::string error;
  ASSERT_TRUE(us4::ScalarMatmul(lhs, rhs, scalarOut, &error)) << error;
  ASSERT_TRUE(us4::NeonMatmul(lhs, rhs, neonOut, &error)) << error;

  const float *scalarData = scalarOut.DataAsFloat32();
  const float *neonData = neonOut.DataAsFloat32();
  for (std::size_t i = 0; i < scalarOut.ElementCount(); ++i) {
    EXPECT_NEAR(neonData[i], scalarData[i], 1e-4F) << i;
  }
}

TEST(KernelNumericsContractTest, MatmulRejectsInnerDimensionMismatch) {
  const us4::Tensor lhs = MakeMatrix(2, 3, {1, 2, 3, 4, 5, 6});
  const us4::Tensor rhs = MakeMatrix(2, 2, {1, 2, 3, 4});
  us4::Tensor out({2, 2}, us4::DType::kFloat32);

  std::string error;
  EXPECT_FALSE(us4::ScalarMatmul(lhs, rhs, out, &error));
  EXPECT_FALSE(error.empty());
}

TEST(KernelNumericsContractTest, MatmulRejectsWrongOutputShape) {
  const us4::Tensor lhs = MakeMatrix(2, 3, {1, 2, 3, 4, 5, 6});
  const us4::Tensor rhs = MakeMatrix(3, 2, {7, 8, 9, 10, 11, 12});
  us4::Tensor out({2, 3}, us4::DType::kFloat32);

  std::string error;
  EXPECT_FALSE(us4::ScalarMatmul(lhs, rhs, out, &error));
  EXPECT_FALSE(error.empty());
}

TEST(KernelNumericsContractTest, MatmulRejectsNonFloat32Operands) {
  const us4::Tensor lhs({2, 2}, us4::DType::kInt8);
  const us4::Tensor rhs = MakeMatrix(2, 2, {1, 2, 3, 4});
  us4::Tensor out({2, 2}, us4::DType::kFloat32);

  std::string error;
  EXPECT_FALSE(us4::ScalarMatmul(lhs, rhs, out, &error));
  EXPECT_FALSE(error.empty());
}
