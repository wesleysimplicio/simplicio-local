#include <gtest/gtest.h>

#include <vector>

#include "cache/multimodal_cache.h"
#include "cache/sparsity_aware_cache.h"
#include "moe/router.h"

namespace {

std::vector<us4::ModalityTokenState> ImageAudioState() {
  return {
      {"image", {"img-a", "img-b"}},
      {"audio", {"aud-a"}},
  };
}

} // namespace

TEST(MoeAdvancedContractTest, MultimodalCacheTracksEntriesPerModality) {
  us4::MultimodalCache cache;

  const us4::MultimodalCacheSnapshot snapshot =
      cache.Touch("minimax", ImageAudioState());

  EXPECT_EQ(snapshot.entryCount, 2U);
  EXPECT_EQ(snapshot.activeModalities, 2U);
  EXPECT_EQ(snapshot.lastTouchHits, 0U);
  EXPECT_EQ(snapshot.lastTouchMisses, 2U);
  EXPECT_EQ(snapshot.missCount, 2U);
  EXPECT_EQ(cache.EntryCount(), 2U);
  EXPECT_EQ(snapshot.lastModalities,
            (std::vector<std::string>{"image", "audio"}));
}

TEST(MoeAdvancedContractTest, MultimodalCacheCountsRepeatTouchAsHit) {
  us4::MultimodalCache cache;

  cache.Touch("minimax", ImageAudioState());
  const us4::MultimodalCacheSnapshot second =
      cache.Touch("minimax", ImageAudioState());

  EXPECT_EQ(second.entryCount, 2U);
  EXPECT_EQ(second.lastTouchHits, 2U);
  EXPECT_EQ(second.lastTouchMisses, 0U);
  EXPECT_EQ(second.hitCount, 2U);
  EXPECT_GT(second.hitRatio, 0.0);
}

TEST(MoeAdvancedContractTest, MultimodalCacheIsolatesAcrossFamilies) {
  us4::MultimodalCache cache;

  cache.Touch("minimax", ImageAudioState());
  const us4::MultimodalCacheSnapshot other =
      cache.Touch("gemma", ImageAudioState());

  EXPECT_EQ(other.entryCount, 4U);
  EXPECT_EQ(other.lastTouchHits, 0U);
  EXPECT_EQ(other.lastTouchMisses, 2U);
}

TEST(MoeAdvancedContractTest, SparsityCacheReusesEntryForIdenticalRouting) {
  us4::Router router;
  us4::SparsityAwareCache cache;
  const us4::RouterDecision routing =
      router.RouteTopK({1.3F, 0.8F, 0.6F, 0.1F}, 2);

  const us4::SparsityCacheSnapshot first = cache.Touch("glm", routing);
  const us4::SparsityCacheSnapshot second = cache.Touch("glm", routing);

  EXPECT_FALSE(first.lastLookupHit);
  EXPECT_TRUE(second.lastLookupHit);
  EXPECT_EQ(cache.EntryCount(), 1U);
  ASSERT_TRUE(cache.Lookup("glm", routing).has_value());
  EXPECT_EQ(cache.Lookup("glm", routing)->experts.size(), 2U);
}

TEST(MoeAdvancedContractTest, SparsityCacheKeepsFamiliesPartitioned) {
  us4::Router router;
  us4::SparsityAwareCache cache;
  const us4::RouterDecision routing =
      router.RouteTopK({1.4F, 0.9F, 0.7F, 0.2F}, 2);

  cache.Touch("deepseek", routing);
  const us4::SparsityCacheSnapshot otherFamily = cache.Touch("kimi", routing);

  EXPECT_FALSE(otherFamily.lastLookupHit);
  EXPECT_EQ(otherFamily.entryCount, 2U);
  EXPECT_FALSE(cache.Lookup("qwen", routing).has_value());
}
