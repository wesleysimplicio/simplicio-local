#include <gtest/gtest.h>

#include <algorithm>
#include <string>

#include "core/hardware_probe.h"

TEST(IsaDetectionContractTest, SnapshotIsSelfDescribingAndSorted) {
  const us4::HardwareProbeResult probe = us4::HardwareProbe::Detect();
  EXPECT_FALSE(probe.isaSource.empty());
  EXPECT_FALSE(probe.isaReason.empty());
  EXPECT_TRUE(std::is_sorted(probe.isaFeatures.begin(), probe.isaFeatures.end()));
  if (probe.hasAvx2) {
    EXPECT_TRUE(probe.hasAvx);
    EXPECT_TRUE(probe.osAvxEnabled);
  }
  if (probe.hasAvx512F) {
    EXPECT_TRUE(probe.osAvx512Enabled);
  }
}
