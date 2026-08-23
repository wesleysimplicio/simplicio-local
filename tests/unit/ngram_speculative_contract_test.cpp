#include <gtest/gtest.h>

#include "speculative/ngram_speculative.h"

TEST(NgramSpeculativeContractTest, RequiresExplicitBackendCapability) {
  const auto unknown = us4::DiscoverNgramPromptLookupBackend(
      "llama.cpp", "unknown", false);
  EXPECT_FALSE(unknown.supported);
  EXPECT_EQ(unknown.reason, "backend-did-not-advertise-prompt-lookup");

  const auto supported = us4::DiscoverNgramPromptLookupBackend(
      "llama.cpp", "b4000", true);
  EXPECT_TRUE(supported.supported);
  EXPECT_EQ(supported.version, "b4000");
}

TEST(NgramSpeculativeContractTest, UsesNearestEarlierContinuation) {
  const auto result = us4::BuildNgramPromptLookupDraft(
      {1, 2, 9, 8, 1, 2}, {.ngramSize = 2, .maxDraftTokens = 2});

  ASSERT_TRUE(result.supported);
  EXPECT_EQ(result.matchedPosition, 0U);
  ASSERT_EQ(result.tokens.size(), 2U);
  EXPECT_EQ(result.tokens[0], 9);
  EXPECT_EQ(result.tokens[1], 8);
}

TEST(NgramSpeculativeContractTest, DoesNotUseCurrentSuffixAsItsOwnMatch) {
  const auto result = us4::BuildNgramPromptLookupDraft(
      {1, 2, 3, 4}, {.ngramSize = 2, .maxDraftTokens = 4});
  EXPECT_FALSE(result.supported);
  EXPECT_EQ(result.reason, "no-earlier-ngram-match");
}

TEST(NgramSpeculativeContractTest, InvalidAndShortInputsFailClosed) {
  EXPECT_FALSE(us4::BuildNgramPromptLookupDraft(
                   {1, 2, 3}, {.ngramSize = 0, .maxDraftTokens = 2})
                   .supported);
  EXPECT_EQ(us4::BuildNgramPromptLookupDraft(
                {1, 2}, {.ngramSize = 2, .maxDraftTokens = 2})
                .reason,
            "history-too-short");
}
