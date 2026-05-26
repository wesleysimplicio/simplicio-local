#include <gtest/gtest.h>

#include "memory/unified_allocator.h"

TEST(MemoryContractTest, CpuOnlyAllocationTagsVisibilityAndBytes) {
  us4::UnifiedAllocator allocator;

  const auto allocation = allocator.Allocate(128U, false);

  ASSERT_NE(allocation, nullptr);
  EXPECT_EQ(allocation->bytes.size(), 128U);
  EXPECT_TRUE(allocation->cpuVisible);
  EXPECT_FALSE(allocation->gpuVisible);
  EXPECT_EQ(allocation->visibility, us4::AllocationVisibility::kCpuOnly);
  EXPECT_EQ(allocator.AllocationCount(), 1U);
  EXPECT_EQ(allocator.ResidentBytes(), 128U);
  EXPECT_EQ(allocator.SharedAllocationCount(), 0U);
}

TEST(MemoryContractTest, SharedAllocationIsGpuVisibleAndCounted) {
  us4::UnifiedAllocator allocator;

  allocator.Allocate(64U, false);
  const auto shared = allocator.Allocate(256U, true);

  ASSERT_NE(shared, nullptr);
  EXPECT_TRUE(shared->gpuVisible);
  EXPECT_EQ(shared->visibility, us4::AllocationVisibility::kUnifiedShared);
  EXPECT_EQ(allocator.AllocationCount(), 2U);
  EXPECT_EQ(allocator.ResidentBytes(), 320U);
  EXPECT_EQ(allocator.SharedAllocationCount(), 1U);
}

TEST(MemoryContractTest, VisibilityStringsAreDistinct) {
  EXPECT_NE(us4::ToString(us4::AllocationVisibility::kCpuOnly),
            us4::ToString(us4::AllocationVisibility::kUnifiedShared));
  EXPECT_FALSE(us4::ToString(us4::AllocationVisibility::kCpuOnly).empty());
}

TEST(MemoryContractTest, ZeroByteAllocationStaysTracked) {
  us4::UnifiedAllocator allocator;

  const auto allocation = allocator.Allocate(0U, false);

  ASSERT_NE(allocation, nullptr);
  EXPECT_TRUE(allocation->bytes.empty());
  EXPECT_EQ(allocator.AllocationCount(), 1U);
  EXPECT_EQ(allocator.ResidentBytes(), 0U);
}
