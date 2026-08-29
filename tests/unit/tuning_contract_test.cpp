#include <gtest/gtest.h>

#include "core/hardware_probe.h"
#include "tuning/auto_tuner.h"
#include "tuning/profile_cache.h"

TEST(TuningContractTest, AutoTunerPicksLowestLatencyCandidate) {
  us4::HardwareProbeResult hardware;
  hardware.chip = "M3";
  const std::vector<us4::AutoTunerCandidate> candidates = {
      {4U, 16U, 1U, 9.5F},
      {8U, 8U, 2U, 4.2F},
      {16U, 16U, 4U, 6.1F},
  };
  const auto profile = us4::SelectAutoTunerProfile(hardware, candidates);
  EXPECT_EQ(profile.tileRows, 8U);
  EXPECT_EQ(profile.tileCols, 8U);
  EXPECT_EQ(profile.batchSize, 2U);
  EXPECT_FLOAT_EQ(profile.estimatedLatencyMs, 4.2F);
  EXPECT_EQ(profile.chip, "M3");
}

TEST(TuningContractTest, AutoTunerHandlesEmptyCandidates) {
  us4::HardwareProbeResult hardware;
  hardware.chip = "M5";
  const auto profile = us4::SelectAutoTunerProfile(hardware, {});
  EXPECT_EQ(profile.tileRows, 0U);
  EXPECT_EQ(profile.chip, "M5");
}

TEST(TuningContractTest, ProfileCacheStoresAndLooksUp) {
  us4::ProfileCache cache;
  us4::ProfileCacheKey key{"M3", "qwen-0.5b"};
  us4::AutoTunerProfile profile;
  profile.chip = "M3";
  profile.tileRows = 8U;
  profile.tileCols = 16U;
  profile.batchSize = 4U;
  profile.estimatedLatencyMs = 3.1F;
  profile.speculativeLookaheadTokens = 2U;
  profile.speculativeWarmupRuns = 3U;
  profile.learnedPinnedExperts = 1U;
  cache.Store(key, profile);

  EXPECT_EQ(cache.Size(), 1U);
  const auto retrieved = cache.Lookup(key);
  ASSERT_TRUE(retrieved.has_value());
  EXPECT_EQ(retrieved->batchSize, 4U);
  EXPECT_EQ(retrieved->speculativeLookaheadTokens, 2U);
  EXPECT_EQ(retrieved->speculativeWarmupRuns, 3U);
  EXPECT_EQ(retrieved->learnedPinnedExperts, 1U);
}

TEST(TuningContractTest, ProfileCacheSerializeAndLoadRoundTrip) {
  us4::ProfileCache cache;
  us4::AutoTunerProfile profileA{"M3", 8U, 16U, 4U, 3.1F, 2U, 3U, 1U};
  us4::AutoTunerProfile profileB{"M5", 16U, 16U, 8U, 1.4F, 4U, 1U, 2U};
  cache.Store({"M3", "qwen-0.5b"}, profileA);
  cache.Store({"M5", "llama-3.1-8b"}, profileB);
  const std::string serialised = cache.Serialize();

  us4::ProfileCache restored;
  ASSERT_TRUE(restored.Load(serialised));
  EXPECT_EQ(restored.Size(), 2U);
  const auto roundTrip = restored.Lookup({"M5", "llama-3.1-8b"});
  ASSERT_TRUE(roundTrip.has_value());
  EXPECT_EQ(roundTrip->tileRows, 16U);
  EXPECT_EQ(roundTrip->batchSize, 8U);
  EXPECT_EQ(roundTrip->speculativeLookaheadTokens, 4U);
  EXPECT_EQ(roundTrip->speculativeWarmupRuns, 1U);
  EXPECT_EQ(roundTrip->learnedPinnedExperts, 2U);
}

TEST(TuningContractTest, ProfileCacheRejectsMalformedBody) {
  us4::ProfileCache cache;
  EXPECT_FALSE(cache.Load("not-a-real-entry\n"));
}

TEST(TuningContractTest, BoundedAutotuneRequiresCorrectFastNonRegressiveCandidate) {
  us4::HardwareProbeResult hardware;
  const std::vector<us4::AutoTunerCandidate> candidates = {
      {1U, 1U, 1U, 10.0F, "scalar"},
      {8U, 8U, 1U, 10.0F, "avx2"},
      {8U, 8U, 1U, 10.0F, "regressive"},
  };
  const auto result = us4::RunBoundedAutoTune(
      hardware, candidates,
      [](const us4::AutoTunerCandidate& candidate) {
        if (candidate.name == "scalar") {
          return us4::AutoTunerObservation{"scalar", 10.0F, 11.0F, 4U, true, true};
        }
        if (candidate.name == "avx2") {
          return us4::AutoTunerObservation{"avx2", 7.0F, 11.5F, 4U, true, true};
        }
        return us4::AutoTunerObservation{"regressive", 5.0F, 20.0F, 4U, true, true};
      });
  EXPECT_TRUE(result.promoted);
  EXPECT_EQ(result.selectedKernel, "avx2");
  EXPECT_EQ(result.reason, "bounded-autotune-promoted");
}

TEST(TuningContractTest, ProfileCacheKeyIncludesPhysicalIdentity) {
  us4::ProfileCache cache;
  us4::AutoTunerProfile profile;
  profile.chip = "M3";
  us4::ProfileCacheKey avx2{"M3", "model", "machine-a", "avx2", "cpu",
                            "digest-a", "matmul", "int8", "decode", "v1",
                            "kernel-v1", "layout-v1"};
  us4::ProfileCacheKey scalar = avx2;
  scalar.isa = "scalar";
  cache.Store(avx2, profile);
  cache.Store(scalar, profile);
  EXPECT_EQ(cache.Size(), 2U);
  EXPECT_NE(cache.Serialize().find("hardware=machine-a"), std::string::npos);
}
