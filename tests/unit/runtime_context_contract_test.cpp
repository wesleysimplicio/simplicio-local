#include <gtest/gtest.h>

#include "core/hardware_probe.h"
#include "core/runtime_context.h"
#include "core/runtime_mode.h"

namespace {

// A nominal-thermal Apple Silicon probe: performance cores + ample memory and
// no ANE keep the thermal monitor out of the elevated/critical caps, so the
// runtime mode passes through unchanged.
us4::HardwareProbeResult NominalProbe() {
  us4::HardwareProbeResult probe;
  probe.platform = "macos";
  probe.architecture = "arm64";
  probe.isAppleSilicon = true;
  probe.hasMetal = true;
  probe.hasNeon = true;
  probe.hasPerformanceCores = true;
  probe.unifiedMemoryGiB = 64;
  probe.recommendedMode = us4::RuntimeMode::kBalancedPlus;
  return probe;
}

} // namespace

TEST(RuntimeContextContractTest,
     ConstructionAdoptsRecommendedModeUnderNominalThermal) {
  us4::RuntimeContext context(NominalProbe());

  EXPECT_EQ(context.mode(), us4::RuntimeMode::kBalancedPlus);
  EXPECT_EQ(context.backend(), us4::BackendType::kScalarCpu);
  EXPECT_EQ(context.hardware().unifiedMemoryGiB, 64U);
}

TEST(RuntimeContextContractTest, SetModePassesThroughWhenThermalIsNominal) {
  us4::RuntimeContext context(NominalProbe());

  context.SetMode(us4::RuntimeMode::kDegraded);
  EXPECT_EQ(context.mode(), us4::RuntimeMode::kDegraded);

  context.SetMode(us4::RuntimeMode::kNano);
  EXPECT_EQ(context.mode(), us4::RuntimeMode::kNano);
}

TEST(RuntimeContextContractTest, SetBackendOverridesSelection) {
  us4::RuntimeContext context(NominalProbe());

  context.SetBackend(us4::BackendType::kNeon);
  EXPECT_EQ(context.backend(), us4::BackendType::kNeon);
}

TEST(RuntimeContextContractTest, ThermalMonitorClampsModeForConstrainedHost) {
  us4::HardwareProbeResult probe = NominalProbe();
  probe.hasPerformanceCores = false; // efficiency-only -> thermal critical cap
  probe.unifiedMemoryGiB = 8;
  probe.recommendedMode = us4::RuntimeMode::kFull;

  us4::RuntimeContext context(probe);

  // Critical thermal caps the runtime well below the requested FULL mode.
  EXPECT_NE(context.mode(), us4::RuntimeMode::kFull);
  EXPECT_GE(us4::RuntimeModeRank(us4::RuntimeMode::kFull),
            us4::RuntimeModeRank(context.mode()));
}

TEST(RuntimeContextContractTest, ExposesSharedRuntimeSubsystems) {
  us4::RuntimeContext context(NominalProbe());

  // Allocations made through the context allocator are observable on it.
  context.allocator().Allocate(32U, false);
  EXPECT_EQ(context.allocator().AllocationCount(), 1U);

  // Router and expert pager are live and wired.
  EXPECT_EQ(context.router().TopK({0.2F, 0.9F, 0.5F}, 2).size(), 2U);
  context.expertPager().Touch("expert-a");
  EXPECT_TRUE(context.expertPager().IsResident("expert-a"));
}
