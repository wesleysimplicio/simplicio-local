#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace us4 {

class KernelRegistry;

// Column-major RHS packing removes the gather/manual packing from the inner
// dot-product loop. The source dimensions and digest are retained so callers
// can key a persistent packed artifact safely.
struct PackedInt8Matrix {
  static constexpr const char* kLayoutVersion = "int8-column-major/v1";

  std::size_t rows = 0;
  std::size_t columns = 0;
  std::vector<std::int8_t> values;
  std::string source_digest;
  bool valid = false;
  std::string reason;
};

PackedInt8Matrix PackInt8Rhs(const std::int8_t* rhs, std::size_t rows,
                             std::size_t columns);
bool ValidatePackedInt8Rhs(const PackedInt8Matrix& packed,
                           std::size_t rows, std::size_t columns);

// All public entry points remain callable on every target. On a target that
// cannot compile AVX2 they execute the same scalar reference algorithm.
void Avx2Int8Matmul(const std::int8_t* lhs, const std::int8_t* rhs,
                    std::size_t lhsRows, std::size_t lhsCols,
                    std::size_t rhsCols, float* output);
void Avx2Int8MatmulPacked(const std::int8_t* lhs,
                          const PackedInt8Matrix& packed,
                          std::size_t lhsRows, std::size_t lhsCols,
                          float* output);

// Q4 format: two unsigned nibbles per byte, laid out as row-major
// [inner][output-column]. A nibble is centered at eight and multiplied by
// one scale per output column.
void Avx2Q4Matmul(const std::int8_t* lhs, const std::uint8_t* packed_rhs,
                  const float* scales, std::size_t lhsRows,
                  std::size_t lhsCols, std::size_t rhsCols, float* output);

void RegisterCpuInt8Kernels(KernelRegistry& registry);

}  // namespace us4
