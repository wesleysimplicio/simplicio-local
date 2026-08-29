#include <gtest/gtest.h>

#include "cpu/advanced_dispatch.h"

namespace {

us4::AdvancedInt8Request Request() {
  us4::AdvancedInt8Request request;
  request.hardware.architecture = "x64";
  request.hardware.hasAvx2 = true;
  request.hardware.hasAvx512Vnni = true;
  request.rows = 8U;
  request.inner = 256U;
  request.columns = 8U;
  request.observations = {
      {.kernel = us4::CpuInt8Kernel::kScalar,
       .compiled = true,
       .numerically_correct = true,
       .p50_ms = 10.0,
       .p95_ms = 11.0},
      {.kernel = us4::CpuInt8Kernel::kX86Avx2,
       .compiled = true,
       .numerically_correct = true,
       .p50_ms = 8.0,
       .p95_ms = 9.0},
      {.kernel = us4::CpuInt8Kernel::kX86Vnni,
       .compiled = true,
       .numerically_correct = false,
       .p50_ms = 1.0,
       .p95_ms = 2.0},
  };
  return request;
}

}  // namespace

TEST(AdvancedDispatchContractTest, CorrectnessGateWinsOverFasterCandidate) {
  const auto selection = us4::SelectAdvancedInt8Kernel(Request());
  EXPECT_EQ(selection.effective_kernel, us4::CpuInt8Kernel::kX86Avx2);
  EXPECT_TRUE(selection.promoted);
  EXPECT_FALSE(selection.fallback);
}

TEST(AdvancedDispatchContractTest, ThermalOrMissingMeasurementFallsBack) {
  auto request = Request();
  request.observations[1].thermal_throttled = true;
  const auto selection = us4::SelectAdvancedInt8Kernel(request);
  EXPECT_EQ(selection.effective_kernel, us4::CpuInt8Kernel::kScalar);
  EXPECT_TRUE(selection.fallback);
  EXPECT_NE(selection.reason.find("baseline"), std::string::npos);
}

TEST(AdvancedDispatchContractTest, OsAndIsaCapabilityAreRequired) {
  auto request = Request();
  request.hardware.hasAvx2 = false;
  const auto selection = us4::SelectAdvancedInt8Kernel(request);
  EXPECT_EQ(selection.effective_kernel, us4::CpuInt8Kernel::kScalar);
  EXPECT_TRUE(selection.fallback);
}
