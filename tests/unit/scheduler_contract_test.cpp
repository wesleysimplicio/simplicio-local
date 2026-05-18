#include <gtest/gtest.h>

#include "scheduler/continuous_batcher.h"
#include "scheduler/session_pool.h"
#include "speculative/draft_model_loader.h"
#include "speculative/eagle3_decoder.h"
#include "speculative/peagle_decoder.h"
#include "speculative/speculative_telemetry.h"

TEST(SchedulerContractTest, ContinuousBatcherAlternatesSessions) {
  us4::ContinuousBatcher batcher(/*fairnessQuantum=*/1);
  batcher.Submit({"a", "prompt-a-1"});
  batcher.Submit({"a", "prompt-a-2"});
  batcher.Submit({"b", "prompt-b-1"});

  const auto first = batcher.NextToken();
  ASSERT_TRUE(first.has_value());
  EXPECT_EQ(first->sessionId, "a");

  const auto second = batcher.NextToken();
  ASSERT_TRUE(second.has_value());
  EXPECT_EQ(second->sessionId, "b");

  const auto third = batcher.NextToken();
  ASSERT_TRUE(third.has_value());
  EXPECT_EQ(third->sessionId, "a");
}

TEST(SchedulerContractTest, ContinuousBatcherDegradesToFifoForSingleSession) {
  us4::ContinuousBatcher batcher;
  batcher.Submit({"only", "prompt-1"});
  batcher.Submit({"only", "prompt-2"});

  const auto first = batcher.NextToken();
  const auto second = batcher.NextToken();
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  EXPECT_EQ(first->prompt, "prompt-1");
  EXPECT_EQ(second->prompt, "prompt-2");
}

TEST(SchedulerContractTest, SessionPoolIsolatesKvNamespace) {
  us4::SessionPool pool;
  auto &alice = pool.GetOrCreate("alice");
  auto &bob = pool.GetOrCreate("bob");
  EXPECT_NE(alice.kvNamespace, bob.kvNamespace);

  pool.AppendRollingContext("alice", {0.1F, 0.2F});
  pool.AppendRollingContext("bob", {0.9F});
  EXPECT_EQ(pool.Snapshot("alice")->rollingContext.size(), 2U);
  EXPECT_EQ(pool.Snapshot("bob")->rollingContext.size(), 1U);
  EXPECT_FALSE(pool.Snapshot("ghost").has_value());
}

TEST(SchedulerContractTest, PEagleAcceptsDraftWithinTolerance) {
  us4::PEagleDecoder decoder(/*verifyWindow=*/3);
  const std::vector<us4::SpeculativeDraftToken> drafts = {
      {"hello", 1.0F, 1.0F},
      {"world", 0.5F, 0.5F},
      {"!", 0.4F, 0.4F},
  };
  const auto result = decoder.Verify(drafts);
  EXPECT_EQ(result.accepted, 3U);
  EXPECT_TRUE(result.acceptedTokens == drafts[0].token ||
              result.acceptedTokens.front() == drafts[0].token);
}

TEST(SchedulerContractTest, PEagleRejectsHalfwayWhenDraftDivergesFromTarget) {
  us4::PEagleDecoder decoder(/*verifyWindow=*/3);
  const std::vector<us4::SpeculativeDraftToken> drafts = {
      {"good", 0.4F, 0.4F},
      {"bad", 1.0F, 0.0F}, // diverges from target
      {"unreached", 0.4F, 0.4F},
  };
  const auto result = decoder.Verify(drafts);
  EXPECT_EQ(result.accepted, 1U);
  EXPECT_EQ(result.rejectedAt, 1U);
}

TEST(SchedulerContractTest, Eagle3RemembersAndPredictsNGrams) {
  us4::Eagle3Decoder decoder;
  decoder.RememberNGram({"hello", "world"});
  decoder.RememberNGram({"hello", "us4"});

  const auto predictions = decoder.PredictFromContext({"hello"}, 4U);
  EXPECT_FALSE(predictions.empty());
}

TEST(SchedulerContractTest, DraftLoaderRejectsIncompleteManifest) {
  const std::string body = "family=qwen\nmodel_id=qwen-0.5b-draft\n";
  EXPECT_FALSE(us4::ParseDraftModelManifestBody(body).has_value());
}

TEST(SchedulerContractTest, DraftLoaderParsesCompleteManifest) {
  const std::string body =
      "family=qwen\n"
      "model_id=qwen-0.5b-draft\n"
      "tokenizer_hash=abc123\n"
      "file=draft/qwen-0.5b-draft.gguf\n"
      "weight_format=gguf\n";
  const auto parsed = us4::ParseDraftModelManifestBody(body);
  ASSERT_TRUE(parsed.has_value());
  EXPECT_EQ(parsed->family, "qwen");
  EXPECT_EQ(parsed->tokenizerHash, "abc123");
}

TEST(SchedulerContractTest, SpeculativeTelemetryReportsAcceptanceRate) {
  const auto telemetry = us4::ComputeSpeculativeTelemetry(10U, 6U, 4U);
  EXPECT_EQ(telemetry.draftAttempts, 10U);
  EXPECT_EQ(telemetry.acceptedTokens, 6U);
  EXPECT_EQ(telemetry.rejectedTokens, 4U);
  EXPECT_FLOAT_EQ(telemetry.acceptanceRate, 0.6F);
}
