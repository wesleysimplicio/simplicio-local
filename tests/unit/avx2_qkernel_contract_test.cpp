#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "core/kernel_registry.h"
#include "cpu/avx2_kernels.h"
#include "cpu/int8_matmul.h"

namespace {

std::vector<std::int8_t> MakeValues(std::size_t count, int offset) {
  std::vector<std::int8_t> values(count);
  for (std::size_t index = 0; index < count; ++index) {
    values[index] = static_cast<std::int8_t>(
        static_cast<int>(index % 19U) - offset);
  }
  return values;
}

}  // namespace

TEST(Avx2QKernelContractTest, PackedQ8MatchesScalarIncludingTails) {
  constexpr std::size_t rows = 3U;
  constexpr std::size_t inner = 37U;
  constexpr std::size_t columns = 5U;
  const auto lhs = MakeValues(rows * inner, 8);
  const auto rhs = MakeValues(inner * columns, 6);
  const auto packed = us4::PackInt8Rhs(rhs.data(), inner, columns);
  ASSERT_TRUE(packed.valid);
  ASSERT_TRUE(us4::ValidatePackedInt8Rhs(packed, inner, columns));
  std::vector<float> scalar(rows * columns);
  std::vector<float> avx2(rows * columns);
  us4::ScalarInt8Matmul(lhs.data(), rhs.data(), rows, inner, columns,
                        scalar.data());
  us4::Avx2Int8MatmulPacked(lhs.data(), packed, rows, inner, avx2.data());
  for (std::size_t index = 0; index < scalar.size(); ++index) {
    EXPECT_FLOAT_EQ(scalar[index], avx2[index]) << index;
  }
}

TEST(Avx2QKernelContractTest, Q4NibblesApplySignedCenterAndScale) {
  constexpr std::size_t rows = 1U;
  constexpr std::size_t inner = 7U;
  constexpr std::size_t columns = 3U;
  const std::int8_t lhs[inner] = {1, -2, 3, -4, 5, -6, 7};
  const std::uint8_t packed[inner * ((columns + 1U) / 2U)] = {
      0x98, 0x07, 0x6A, 0xF1, 0x23, 0x45, 0x67, 0x89,
      0xAB, 0xCD, 0xEF, 0x10, 0x32, 0x54, 0x76, 0x98};
  const float scales[columns] = {1.0F, 0.5F, 2.0F};
  std::vector<float> output(columns);
  us4::Avx2Q4Matmul(lhs, packed, scales, rows, inner, columns, output.data());
  for (std::size_t column = 0; column < columns; ++column) {
    int expected = 0;
    for (std::size_t index = 0; index < inner; ++index) {
      const auto byte = packed[index * 2U + column / 2U];
      const int nibble = (column % 2U == 0U) ? (byte & 0x0F) : (byte >> 4U);
      expected += static_cast<int>(lhs[index]) * (nibble - 8);
    }
    EXPECT_FLOAT_EQ(output[column], static_cast<float>(expected) * scales[column]);
  }
}

TEST(Avx2QKernelContractTest, RegistryCarriesThePhysicalAvx2Pointer) {
  us4::KernelRegistry registry;
  us4::RegisterCpuInt8Kernels(registry);
  const auto selected = registry.Select(us4::KernelOperation::kInt8Matmul,
                                        "avx2", {"avx2"});
  ASSERT_NE(selected.implementation, nullptr);
  EXPECT_EQ(selected.effective_kernel, "avx2");
  EXPECT_NE(selected.implementation->int8_matmul, nullptr);
}
