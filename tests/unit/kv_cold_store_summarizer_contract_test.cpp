#include <gtest/gtest.h>

#include <filesystem>
#include <vector>

#include "kv/ssd_cold_store.h"
#include "kv/summarizer.h"

namespace {

std::filesystem::path TempStoreRoot(const char *name) {
  return std::filesystem::temp_directory_path() / "us4-cold-store-tests" / name;
}

} // namespace

TEST(SsdColdStoreContractTest, FlushThenRestoreRoundTripsValues) {
  const auto root = TempStoreRoot("roundtrip");
  std::filesystem::remove_all(root);
  us4::SsdColdStore store(root);

  const std::vector<float> values = {1.0F, -2.5F, 3.25F};
  ASSERT_TRUE(store.Flush("prompt-a", values));

  const auto restored = store.Restore("prompt-a");
  ASSERT_TRUE(restored.has_value());
  ASSERT_EQ(restored->size(), values.size());
  for (std::size_t i = 0; i < values.size(); ++i) {
    EXPECT_FLOAT_EQ((*restored)[i], values[i]) << i;
  }
}

TEST(SsdColdStoreContractTest, RestoreMissingKeyReturnsNullopt) {
  const auto root = TempStoreRoot("missing");
  std::filesystem::remove_all(root);
  us4::SsdColdStore store(root);

  EXPECT_FALSE(store.Restore("never-written").has_value());
}

TEST(SsdColdStoreContractTest, KeysDoNotCollide) {
  const auto root = TempStoreRoot("distinct");
  std::filesystem::remove_all(root);
  us4::SsdColdStore store(root);

  ASSERT_TRUE(store.Flush("a", {1.0F}));
  ASSERT_TRUE(store.Flush("b", {2.0F, 3.0F}));

  const auto a = store.Restore("a");
  const auto b = store.Restore("b");
  ASSERT_TRUE(a.has_value());
  ASSERT_TRUE(b.has_value());
  EXPECT_EQ(a->size(), 1U);
  EXPECT_EQ(b->size(), 2U);
  EXPECT_FLOAT_EQ((*a)[0], 1.0F);
  EXPECT_FLOAT_EQ((*b)[1], 3.0F);
}

TEST(SummarizerContractTest, SummarizeReturnsMean) {
  const us4::Summarizer summarizer;
  const auto summary = summarizer.Summarize({2.0F, 4.0F, 6.0F});

  ASSERT_EQ(summary.size(), 1U);
  EXPECT_FLOAT_EQ(summary[0], 4.0F);
}

TEST(SummarizerContractTest, SummarizeEmptyReturnsEmpty) {
  const us4::Summarizer summarizer;
  EXPECT_TRUE(summarizer.Summarize({}).empty());
}

TEST(SummarizerContractTest, SummarizeRowsAveragesEachColumn) {
  const us4::Summarizer summarizer;
  // Two rows of width 3: [[1,2,3],[3,4,5]] -> column means [2,3,4].
  const auto summary =
      summarizer.SummarizeRows({1.0F, 2.0F, 3.0F, 3.0F, 4.0F, 5.0F}, 3U);

  ASSERT_EQ(summary.size(), 3U);
  EXPECT_FLOAT_EQ(summary[0], 2.0F);
  EXPECT_FLOAT_EQ(summary[1], 3.0F);
  EXPECT_FLOAT_EQ(summary[2], 4.0F);
}

TEST(SummarizerContractTest, SummarizeRowsRejectsNonDivisibleWidth) {
  const us4::Summarizer summarizer;
  EXPECT_TRUE(summarizer.SummarizeRows({1.0F, 2.0F, 3.0F}, 2U).empty());
  EXPECT_TRUE(summarizer.SummarizeRows({1.0F, 2.0F}, 0U).empty());
}
