#include <gtest/gtest.h>

#include <cstdint>

#include "core/kernel_registry.h"

namespace {

void ScalarKernel(const std::int8_t*, const std::int8_t*, std::size_t,
                  std::size_t, std::size_t, float*) {}

void Avx2Kernel(const std::int8_t*, const std::int8_t*, std::size_t,
                std::size_t, std::size_t, float*) {}

}  // namespace

TEST(KernelRegistryContractTest, KeepsOneNamedImplementationAndCatalogIsSorted) {
  us4::KernelRegistry registry;
  EXPECT_TRUE(registry.Register({
      {.name = "avx2", .operation = us4::KernelOperation::kInt8Matmul,
       .dtype = "int8", .isa_requirements = {"avx2"}, .compiled = true,
       .priority = 20},
      .int8_matmul = Avx2Kernel}));
  EXPECT_TRUE(registry.Register({
      {.name = "scalar", .operation = us4::KernelOperation::kInt8Matmul,
       .dtype = "int8", .compiled = true, .portable = true},
      .int8_matmul = ScalarKernel}));
  EXPECT_FALSE(registry.Register({
      {.name = "scalar", .operation = us4::KernelOperation::kInt8Matmul,
       .dtype = "int8", .compiled = true, .portable = true},
      .int8_matmul = ScalarKernel}));
  ASSERT_EQ(registry.Size(), 2U);
  EXPECT_EQ(registry.Catalog()[0].name, "avx2");
}

TEST(KernelRegistryContractTest, SelectionUsesPhysicalFunctionAndScalarKillSwitch) {
  us4::KernelRegistry registry;
  registry.Register({{.name = "scalar", .operation = us4::KernelOperation::kInt8Matmul,
                      .dtype = "int8", .compiled = true, .portable = true},
                     .int8_matmul = ScalarKernel});
  registry.Register({{.name = "avx2", .operation = us4::KernelOperation::kInt8Matmul,
                      .dtype = "int8", .isa_requirements = {"avx2"},
                      .compiled = true, .priority = 10},
                     .int8_matmul = Avx2Kernel});

  const auto selected = registry.Select(us4::KernelOperation::kInt8Matmul,
                                        "avx2", {"avx2"});
  ASSERT_NE(selected.implementation, nullptr);
  EXPECT_EQ(selected.effective_kernel, "avx2");
  EXPECT_FALSE(selected.fallback);
  EXPECT_NE(selected.implementation->int8_matmul, nullptr);

  const auto forced = registry.Select(us4::KernelOperation::kInt8Matmul,
                                      "avx2", {"avx2"}, true);
  EXPECT_EQ(forced.effective_kernel, "scalar");
  EXPECT_TRUE(forced.fallback);
}
