#include <gtest/gtest.h>

#include <cstddef>
#include <cstdint>
#include <vector>

#include "cpu/int8_matmul.h"

namespace {

std::vector<std::int8_t> MakeValues(const std::size_t count,
                                    const std::size_t period,
                                    const int offset) {
  std::vector<std::int8_t> values(count);
  for (std::size_t index = 0; index < count; ++index) {
    values[index] =
        static_cast<std::int8_t>(static_cast<int>(index % period) - offset);
  }
  return values;
}

} // namespace

TEST(CpuInt8DispatchContractTest, KeepsScalarFallbackExplicit) {
  const us4::CpuInt8Dispatch dispatch =
      us4::SelectCpuInt8Kernel(us4::CpuInt8Capabilities{});

  EXPECT_EQ(dispatch.kernel, us4::CpuInt8Kernel::kScalar);
  EXPECT_FALSE(dispatch.accelerated);
  EXPECT_EQ(us4::ToString(dispatch.kernel), "scalar");
}

TEST(CpuInt8DispatchContractTest, SelectsBestAvailableCompiledIsa) {
  EXPECT_EQ(us4::SelectCpuInt8Kernel(
                {.neonSdot = true, .neonI8mm = true, .x86Vnni = true})
                .kernel,
            us4::CpuInt8Kernel::kNeonI8mm);
  EXPECT_EQ(us4::SelectCpuInt8Kernel(
                {.neonSdot = true, .neonI8mm = false, .x86Vnni = true})
                .kernel,
            us4::CpuInt8Kernel::kNeonSdot);
  EXPECT_EQ(us4::SelectCpuInt8Kernel(
                {.neonSdot = false, .neonI8mm = false, .x86Vnni = true})
                .kernel,
            us4::CpuInt8Kernel::kX86Vnni);
}

TEST(CpuInt8DispatchContractTest, ExposesStableKernelNames) {
  EXPECT_EQ(us4::ToString(us4::CpuInt8Kernel::kNeonSdot), "neon-sdot");
  EXPECT_EQ(us4::ToString(us4::CpuInt8Kernel::kNeonI8mm), "neon-i8mm");
  EXPECT_EQ(us4::ToString(us4::CpuInt8Kernel::kX86Vnni), "x86-vnni");
}

TEST(CpuInt8DispatchContractTest, DispatchedKernelMatchesScalarWithTails) {
  constexpr std::size_t kRows = 3U;
  constexpr std::size_t kInner = 37U;
  constexpr std::size_t kColumns = 5U;
  const std::vector<std::int8_t> lhs =
      MakeValues(kRows * kInner, 17U, 8);
  const std::vector<std::int8_t> rhs =
      MakeValues(kInner * kColumns, 13U, 6);
  std::vector<float> scalar(kRows * kColumns);
  std::vector<float> dispatched(kRows * kColumns);

  us4::ScalarInt8Matmul(lhs.data(), rhs.data(), kRows, kInner, kColumns,
                       scalar.data());
  us4::CpuInt8Dispatch dispatch;
  us4::CpuInt8Matmul(lhs.data(), rhs.data(), kRows, kInner, kColumns,
                     dispatched.data(), &dispatch);

  EXPECT_FALSE(us4::ToString(dispatch.kernel).empty());
  for (std::size_t index = 0; index < scalar.size(); ++index) {
    EXPECT_FLOAT_EQ(dispatched[index], scalar[index]) << index;
  }
}
