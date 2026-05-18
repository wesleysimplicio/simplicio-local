#include <gtest/gtest.h>

#include "scheduler/session_pool.h"

namespace {

TEST(SessionPoolContractTest, CreatesStableNamespacePerSession) {
  us4::SessionPool pool;

  const us4::SessionState &alpha = pool.Acquire("alpha");
  const us4::SessionState &beta = pool.Acquire("beta");

  EXPECT_EQ(alpha.kvNamespace, "session::alpha");
  EXPECT_EQ(beta.kvNamespace, "session::beta");
  EXPECT_EQ(alpha.generation, 1U);
  EXPECT_EQ(beta.generation, 1U);
  EXPECT_EQ(pool.ActiveSessionCount(), 2U);
}

TEST(SessionPoolContractTest, NamespacesKvAndPrefixKeysWithoutLeakage) {
  us4::SessionPool pool;

  const std::string alphaKv = pool.NamespacedKvKey("alpha", "prompt");
  const std::string betaKv = pool.NamespacedKvKey("beta", "prompt");
  const std::string alphaPrefix =
      pool.NamespacedPrefixKey("alpha", "hello world");
  const std::string betaPrefix =
      pool.NamespacedPrefixKey("beta", "hello world");

  EXPECT_NE(alphaKv, betaKv);
  EXPECT_NE(alphaPrefix, betaPrefix);
  EXPECT_EQ(alphaKv, "session::alpha::kv::prompt");
  EXPECT_EQ(betaPrefix, "session::beta::prefix::hello world");
}

TEST(SessionPoolContractTest, ReleasesSessionAndPreservesPromptOwnership) {
  us4::SessionPool pool;

  pool.RecordPromptPrefix("alpha", "hello");
  pool.RecordPromptPrefix("beta", "hello");

  const auto alpha = pool.Lookup("alpha");
  const auto beta = pool.Lookup("beta");
  ASSERT_TRUE(alpha.has_value());
  ASSERT_TRUE(beta.has_value());
  EXPECT_EQ(alpha->lastPromptPrefix, "hello");
  EXPECT_EQ(beta->lastPromptPrefix, "hello");
  EXPECT_EQ(alpha->kvNamespace, "session::alpha");
  EXPECT_EQ(beta->kvNamespace, "session::beta");

  EXPECT_TRUE(pool.Release("alpha"));
  EXPECT_FALSE(pool.Lookup("alpha").has_value());
  EXPECT_TRUE(pool.Lookup("beta").has_value());
  EXPECT_EQ(pool.ActiveSessionCount(), 1U);
}

} // namespace
