#include <gtest/gtest.h>

#include "speculative/dflash_speculative.h"

TEST(DFlashSpeculativeContractTest, ParsesQuantizedDescriptor) {
  const auto descriptor = us4::ParseDFlashManifestBody(
      "family=qwen\ntarget_family=qwen\ntarget_model=qwen3.8-27b\n"
      "tokenizer_hash=tok-v1\nfile=dflash-q4.bin\nquantization=q4\n"
      "backend=llama.cpp\nmax_draft_tokens=4\nestimated_memory_gib=2\n");
  ASSERT_TRUE(descriptor.has_value());
  EXPECT_EQ(descriptor->quantization, us4::DFlashQuantization::kInt4);
  EXPECT_EQ(descriptor->maxDraftTokens, 4U);
}

TEST(DFlashSpeculativeContractTest, RequiresExactTargetCompatibility) {
  const auto descriptor = us4::ParseDFlashManifestBody(
      "family=qwen\ntarget_family=qwen\ntarget_model=qwen3.8-27b\n"
      "tokenizer_hash=tok-v1\nfile=d.bin\nquantization=fp16\n"
      "backend=llama.cpp\n");
  ASSERT_TRUE(descriptor.has_value());
  const auto result = us4::ValidateDFlashCompatibility(
      *descriptor, {.targetFamily = "qwen",
                     .targetModel = "qwen3.8-27b",
                     .targetTokenizerHash = "tok-v1",
                     .targetBackend = "llama.cpp",
                     .availableMemoryGiB = 8,
                     .allowQuantizedDraft = true});
  EXPECT_TRUE(result.compatible);
  EXPECT_EQ(result.placement, "target-backend");
}

TEST(DFlashSpeculativeContractTest, RejectsBudgetAndTokenizerMismatches) {
  const auto descriptor = us4::ParseDFlashManifestBody(
      "family=qwen\ntarget_family=qwen\ntarget_model=qwen3.8-27b\n"
      "tokenizer_hash=tok-v1\nfile=d.bin\nquantization=q4\n"
      "estimated_memory_gib=4\n");
  ASSERT_TRUE(descriptor.has_value());
  auto request = us4::DFlashCompatibilityRequest{
      .targetFamily = "qwen",
      .targetModel = "qwen3.8-27b",
      .targetTokenizerHash = "wrong",
      .availableMemoryGiB = 2};
  EXPECT_EQ(us4::ValidateDFlashCompatibility(*descriptor, request).reason,
            "tokenizer-hash-mismatch");
  request.targetTokenizerHash = "tok-v1";
  EXPECT_EQ(us4::ValidateDFlashCompatibility(*descriptor, request).reason,
            "memory-budget-insufficient");
}

TEST(DFlashSpeculativeContractTest, TelemetryIsClampedAndComputesAcceptance) {
  const auto telemetry = us4::ComputeDFlashTelemetry(4, 6, 20.0, 12.5);
  EXPECT_EQ(telemetry.acceptedTokens, 4U);
  EXPECT_EQ(telemetry.rejectedTokens, 0U);
  EXPECT_DOUBLE_EQ(telemetry.acceptanceRate, 1.0);
  EXPECT_DOUBLE_EQ(telemetry.draftTokensPerSecond, 20.0);
}
