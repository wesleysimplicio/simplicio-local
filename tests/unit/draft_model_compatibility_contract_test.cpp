#include <gtest/gtest.h>

#include "speculative/draft_model_loader.h"

namespace {

us4::DraftModelDescriptor Draft() {
  us4::DraftModelDescriptor draft;
  draft.family = "qwen";
  draft.modelId = "qwen-draft-0.5b";
  draft.tokenizerHash = "tok-v1";
  draft.filePath = "draft.gguf";
  draft.weightFormat = "gguf";
  draft.architecture = "qwen2";
  draft.vocabularySize = 151936;
  draft.backend = "llama.cpp";
  draft.device = "cpu";
  return draft;
}

} // namespace

TEST(DraftModelCompatibilityContractTest, AcceptsCompatiblePairOnSeparateDevices) {
  const auto result = us4::ValidateDraftModelCompatibility(
      Draft(), {.targetFamily = "qwen",
                 .targetTokenizerHash = "tok-v1",
                 .targetArchitecture = "qwen2",
                 .targetVocabularySize = 151936,
                 .targetBackend = "llama.cpp",
                 .targetDevice = "cuda:0",
                 .allowSeparateDevice = true});
  EXPECT_TRUE(result.compatible);
  EXPECT_EQ(result.draftDevice, "cpu");
}

TEST(DraftModelCompatibilityContractTest, RejectsTokenizerAndVocabularyMismatch) {
  const auto result = us4::ValidateDraftModelCompatibility(
      Draft(), {.targetFamily = "qwen",
                 .targetTokenizerHash = "different",
                 .targetVocabularySize = 32000});
  EXPECT_FALSE(result.compatible);
  ASSERT_EQ(result.reasons.size(), 2U);
  EXPECT_EQ(result.reasons[0], "tokenizer-hash-mismatch");
  EXPECT_EQ(result.reasons[1], "vocabulary-size-mismatch");
}

TEST(DraftModelCompatibilityContractTest, CanForbidSeparateDevicePlacement) {
  const auto result = us4::ValidateDraftModelCompatibility(
      Draft(), {.targetTokenizerHash = "tok-v1",
                 .targetDevice = "cuda:0",
                 .allowSeparateDevice = false});
  EXPECT_FALSE(result.compatible);
  ASSERT_EQ(result.reasons.size(), 1U);
  EXPECT_EQ(result.reasons.front(), "separate-device-not-allowed");
}

TEST(DraftModelLoaderContractTest, ParsesOptionalCompatibilityMetadata) {
  const auto descriptor = us4::ParseDraftModelManifestBody(
      "family=qwen\nmodel_id=draft\ntokenizer_hash=t\nfile=d.gguf\n"
      "weight_format=gguf\ntarget_family=qwen\narchitecture=qwen2\n"
      "vocab_size=151936\nbackend=llama.cpp\ndevice=cuda:1\n");
  ASSERT_TRUE(descriptor.has_value());
  EXPECT_EQ(descriptor->architecture, "qwen2");
  EXPECT_EQ(descriptor->vocabularySize, 151936U);
  EXPECT_EQ(descriptor->device, "cuda:1");
}
