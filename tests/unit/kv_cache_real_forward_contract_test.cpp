#include <filesystem>
#include <string>

#include <gtest/gtest.h>

#include "adapters/adapter_registry.h"
#include "core/hardware_probe.h"
#include "core/model_asset.h"
#include "core/runtime_context.h"

namespace {

us4::HardwareProbeResult MakeProbe() {
  us4::HardwareProbeResult probe;
  probe.platform = "macos";
  probe.architecture = "arm64";
  probe.chip = "apple-m";
  probe.unifiedMemoryGiB = 24;
  probe.hasNeon = true;
  probe.neonVectorBits = 128;
  probe.hasPerformanceCores = true;
  probe.hasEfficiencyCores = true;
  probe.recommendedMode = us4::RuntimeMode::kDegraded;
  return probe;
}

std::filesystem::path RepoRoot() {
#ifdef US4_SOURCE_DIR
  return std::filesystem::path(US4_SOURCE_DIR);
#else
  return std::filesystem::path(__FILE__)
      .parent_path()
      .parent_path()
      .parent_path();
#endif
}

} // namespace

// Issue #81.6: the KV cache must reduce redundant work without changing the
// generated output, and this must hold over a REAL forward (real embedding
// + lm_head weights from #81.4/#81.5), not just the synthetic path.
TEST(KvCacheRealForwardContractTest,
     RepeatedPromptHitsCacheAndReturnsIdenticalRealOutput) {
  const us4::IUS4V6Adapter *adapter = us4::FindAdapterByModel("qwen-0.5b");
  ASSERT_NE(adapter, nullptr);

  us4::ModelAsset asset;
  std::string error;
  const std::filesystem::path tensorPath = RepoRoot() / "tests" / "fixtures" /
                                           "models" / "toy-dense-real" /
                                           "toy-dense-real.safetensors";
  ASSERT_TRUE(us4::LoadModelAsset(tensorPath, asset, &error)) << error;
  ASSERT_TRUE(asset.hasRealWeights) << "fixture must carry real tensors";

  us4::RuntimeContext context(MakeProbe());
  adapter->ConfigureRuntime(context);

  const us4::GenerationResult first = adapter->Generate(
      {.prompt = "alpha", .maxTokens = 1, .asset = &asset}, context);
  const us4::GenerationResult second = adapter->Generate(
      {.prompt = "alpha", .maxTokens = 1, .asset = &asset}, context);

  EXPECT_TRUE(first.usedRealWeights);
  EXPECT_TRUE(second.usedRealWeights);

  // First call populates the KV pager for this prompt prefix; the second
  // call, same context, same prompt, must hit that cache instead of
  // recomputing from scratch.
  EXPECT_FALSE(first.kvCacheHit);
  EXPECT_TRUE(second.kvCacheHit);

  // The whole point of a correct cache: using it must not change the
  // generated output relative to computing it fresh.
  EXPECT_EQ(first.generatedTokens, second.generatedTokens);
  EXPECT_EQ(first.text, second.text);
  EXPECT_EQ(first.text, "delta") << "external-oracle prediction for 'alpha' "
                                    "over these real weights is 'delta'";
}
