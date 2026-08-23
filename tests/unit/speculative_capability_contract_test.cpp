#include <gtest/gtest.h>

#include "core/hardware_probe.h"
#include "speculative/capability.h"

namespace {

us4::ModelAsset Asset() {
  us4::ModelAsset asset;
  asset.family = "qwen";
  asset.modelName = "qwen-fixture";
  return asset;
}

us4::HardwareProbeResult Hardware() {
  us4::HardwareProbeResult hardware;
  hardware.platform = "linux";
  hardware.architecture = "x64";
  hardware.availableMemoryGiB = 16;
  hardware.hasCuda = true;
  hardware.cudaMemoryGiB = 8;
  return hardware;
}

} // namespace

TEST(SpeculativeCapabilityContractTest, ReportsHardwareAndSafeBaseline) {
  const auto snapshot = us4::DiscoverSpeculativeCapabilities(
      Asset(), Hardware(), "llama.cpp", "b4000");

  EXPECT_EQ(snapshot.schemaVersion,
            "simplicio-local.speculative-capabilities/v1");
  EXPECT_TRUE(snapshot.cpuAvailable);
  EXPECT_TRUE(snapshot.cudaAvailable);
  EXPECT_EQ(snapshot.availableMemoryGiB, 16U);
  EXPECT_EQ(snapshot.gpuMemoryGiB, 8U);
  const auto plan = us4::MakeSpeculativeExecutionPlan(
      snapshot, {.requested = us4::SpeculativeStrategy::kMtp});
  EXPECT_FALSE(plan.usesSpeculation);
  EXPECT_TRUE(plan.usedFallback);
  EXPECT_EQ(plan.selected, us4::SpeculativeStrategy::kBaseline);
}

TEST(SpeculativeCapabilityContractTest,
     DoesNotClaimSupportFromModelNameAlone) {
  auto asset = Asset();
  asset.modelName = "qwen-dflash-mtp";
  const auto snapshot = us4::DiscoverSpeculativeCapabilities(
      asset, Hardware(), "unknown-backend");

  const auto dflash = us4::MakeSpeculativeExecutionPlan(
      snapshot, {.requested = us4::SpeculativeStrategy::kDFlash,
                  .allowFallback = false});
  EXPECT_FALSE(dflash.usesSpeculation);
  EXPECT_EQ(dflash.selected, us4::SpeculativeStrategy::kDFlash);
  EXPECT_NE(dflash.reason.find("unsupported-no-fallback"), std::string::npos);
}

TEST(SpeculativeCapabilityContractTest, DraftRequiresArtifactAndSharedTokenizer) {
  auto asset = Asset();
  asset.draftModelPath = "draft.gguf";
  asset.sharedTokenizer = true;
  const auto snapshot = us4::DiscoverSpeculativeCapabilities(
      asset, Hardware(), "llama.cpp");

  const auto plan = us4::MakeSpeculativeExecutionPlan(
      snapshot, {.requested = us4::SpeculativeStrategy::kDraftModel,
                  .maxDraftTokens = 0});
  EXPECT_TRUE(plan.usesSpeculation);
  EXPECT_EQ(plan.selected, us4::SpeculativeStrategy::kDraftModel);
  EXPECT_EQ(plan.maxDraftTokens, 1U);
}

TEST(SpeculativeCapabilityContractTest, ParsesStableStrategyAliases) {
  us4::SpeculativeStrategy strategy = us4::SpeculativeStrategy::kBaseline;
  EXPECT_TRUE(us4::ParseSpeculativeStrategy("prompt_lookup", &strategy));
  EXPECT_EQ(strategy, us4::SpeculativeStrategy::kNgramPromptLookup);
  EXPECT_TRUE(us4::ParseSpeculativeStrategy("self_speculative", &strategy));
  EXPECT_EQ(strategy, us4::SpeculativeStrategy::kMtp);
  EXPECT_FALSE(us4::ParseSpeculativeStrategy("made-up", &strategy));
}
