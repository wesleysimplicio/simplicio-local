#include <gtest/gtest.h>

#include "speculative/mtp_speculative.h"

TEST(MtpSpeculativeContractTest, RequiresExplicitDescriptorFields) {
  const auto descriptor = us4::ParseMtpManifestBody(
      "family=qwen\nmodel_id=qwen3.8-27b\ntokenizer_hash=tok-v1\n"
      "backend=llama.cpp\nhead_tensor=mtp.head\ndepth=2\n");
  ASSERT_TRUE(descriptor.has_value());
  EXPECT_EQ(descriptor->depth, 2U);
  EXPECT_EQ(descriptor->headTensor, "mtp.head");
}

TEST(MtpSpeculativeContractTest, DetectsMetadataWithoutModelNameHeuristic) {
  us4::ModelAsset asset;
  asset.family = "qwen";
  asset.modelName = "ordinary-name";
  asset.metadata["mtp_depth"] = "3";
  const auto capability = us4::DetectMtpCapability(asset, "llama.cpp");
  EXPECT_TRUE(capability.supported);
  EXPECT_EQ(capability.depth, 3U);

  us4::ModelAsset unknown;
  unknown.modelName = "mtp-model-name-only";
  EXPECT_FALSE(us4::DetectMtpCapability(unknown, "llama.cpp").supported);
}

TEST(MtpSpeculativeContractTest, ValidatesExactTargetAndBackend) {
  const us4::MtpDescriptor descriptor{
      .family = "qwen",
      .modelId = "qwen3.8-27b",
      .tokenizerHash = "tok-v1",
      .backend = "llama.cpp",
      .headTensor = "mtp.head",
      .depth = 2};
  EXPECT_TRUE(us4::ValidateMtpCompatibility(
                  descriptor, {.targetFamily = "qwen",
                                .targetModel = "qwen3.8-27b",
                                .targetTokenizerHash = "tok-v1",
                                .targetBackend = "llama.cpp"})
                  .compatible);
  EXPECT_EQ(us4::ValidateMtpCompatibility(
                descriptor, {.targetFamily = "qwen",
                              .targetModel = "qwen3.8-27b",
                              .targetTokenizerHash = "tok-v1",
                              .targetBackend = "metal"})
                .reason,
            "backend-mismatch");
}

TEST(MtpSpeculativeContractTest, ClampsPlanAndTelemetry) {
  const auto plan = us4::MakeMtpExecutionPlan(
      {.supported = true, .depth = 2, .evidence = "metadata"}, 9);
  EXPECT_TRUE(plan.enabled);
  EXPECT_EQ(plan.maxDraftTokens, 2U);
  const auto telemetry = us4::ComputeMtpTelemetry(4, 6);
  EXPECT_EQ(telemetry.acceptedTokens, 4U);
  EXPECT_DOUBLE_EQ(telemetry.acceptanceRate, 1.0);
}
