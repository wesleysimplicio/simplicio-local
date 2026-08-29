#include "cpu/avx2_kernels.h"

#include <algorithm>
#include <array>
#include <iomanip>
#include <sstream>
#include <utility>

#include "core/kernel_registry.h"
#include "cpu/int8_matmul.h"

#if (defined(__x86_64__) || defined(_M_X64)) && \
    (defined(__GNUC__) || defined(__clang__) || defined(_MSC_VER))
#include <immintrin.h>
#define US4_AVX2_TRANSLATION_UNIT 1
#else
#define US4_AVX2_TRANSLATION_UNIT 0
#endif

#if defined(__GNUC__) || defined(__clang__)
#define US4_TARGET_AVX2 __attribute__((target("avx2")))
#else
#define US4_TARGET_AVX2
#endif

namespace us4 {

namespace {

std::uint64_t Fnv1a(const std::int8_t* data, const std::size_t count) {
  std::uint64_t hash = 1469598103934665603ULL;
  for (std::size_t index = 0; index < count; ++index) {
    hash ^= static_cast<std::uint8_t>(data[index]);
    hash *= 1099511628211ULL;
  }
  return hash;
}

std::string Digest(const std::int8_t* data, const std::size_t count) {
  std::ostringstream stream;
  stream << "fnv1a64:" << std::hex << std::setw(16) << std::setfill('0')
         << Fnv1a(data, count);
  return stream.str();
}

std::int32_t ScalarDotRaw(const std::int8_t* lhs, const std::int8_t* rhs,
                          const std::size_t lhsCols,
                          const std::size_t rhsCols,
                          const std::size_t column) {
  std::int32_t sum = 0;
  for (std::size_t inner = 0; inner < lhsCols; ++inner) {
    sum += static_cast<std::int32_t>(lhs[inner]) *
           static_cast<std::int32_t>(rhs[inner * rhsCols + column]);
  }
  return sum;
}

void ScalarMatmulRaw(const std::int8_t* lhs, const std::int8_t* rhs,
                     const std::size_t lhsRows, const std::size_t lhsCols,
                     const std::size_t rhsCols, float* output) {
  if (lhs == nullptr || rhs == nullptr || output == nullptr) {
    return;
  }
  for (std::size_t row = 0; row < lhsRows; ++row) {
    for (std::size_t column = 0; column < rhsCols; ++column) {
      output[row * rhsCols + column] = static_cast<float>(ScalarDotRaw(
          lhs + row * lhsCols, rhs, lhsCols, rhsCols, column));
    }
  }
}

#if !US4_AVX2_TRANSLATION_UNIT
std::int32_t ScalarDotPacked(const std::int8_t* lhs,
                             const PackedInt8Matrix& packed,
                             const std::size_t lhsCols,
                             const std::size_t column) {
  std::int32_t sum = 0;
  const std::int8_t* rhsColumn = packed.values.data() + column * packed.rows;
  for (std::size_t inner = 0; inner < lhsCols; ++inner) {
    sum += static_cast<std::int32_t>(lhs[inner]) *
           static_cast<std::int32_t>(rhsColumn[inner]);
  }
  return sum;
}
#endif

#if US4_AVX2_TRANSLATION_UNIT
US4_TARGET_AVX2 std::int32_t Avx2Dot(const std::int8_t* lhs,
                                     const std::int8_t* rhs,
                                     const std::size_t count) {
  __m256i accumulator = _mm256_setzero_si256();
  const __m256i ones = _mm256_set1_epi16(1);
  std::size_t index = 0;
  for (; index + 16U <= count; index += 16U) {
    const __m128i lhs8 = _mm_loadu_si128(
        reinterpret_cast<const __m128i*>(lhs + index));
    const __m128i rhs8 = _mm_loadu_si128(
        reinterpret_cast<const __m128i*>(rhs + index));
    const __m256i lhs16 = _mm256_cvtepi8_epi16(lhs8);
    const __m256i rhs16 = _mm256_cvtepi8_epi16(rhs8);
    const __m256i products = _mm256_mullo_epi16(lhs16, rhs16);
    accumulator = _mm256_add_epi32(accumulator,
                                    _mm256_madd_epi16(products, ones));
  }
  alignas(32) std::array<std::int32_t, 8> lanes{};
  _mm256_store_si256(reinterpret_cast<__m256i*>(lanes.data()), accumulator);
  std::int32_t sum = 0;
  for (const std::int32_t lane : lanes) {
    sum += lane;
  }
  for (; index < count; ++index) {
    sum += static_cast<std::int32_t>(lhs[index]) *
           static_cast<std::int32_t>(rhs[index]);
  }
  return sum;
}

US4_TARGET_AVX2 void RunAvx2Packed(const std::int8_t* lhs,
                                    const PackedInt8Matrix& packed,
                                    const std::size_t lhsRows,
                                    const std::size_t lhsCols,
                                    float* output) {
  for (std::size_t row = 0; row < lhsRows; ++row) {
    const std::int8_t* lhsRow = lhs + row * lhsCols;
    for (std::size_t column = 0; column < packed.columns; ++column) {
      const std::int8_t* rhsColumn = packed.values.data() + column * packed.rows;
      output[row * packed.columns + column] =
          static_cast<float>(Avx2Dot(lhsRow, rhsColumn, lhsCols));
    }
  }
}

US4_TARGET_AVX2 std::int32_t Avx2Q4Dot(const std::int8_t* lhs,
                                       const std::uint8_t* packed_rhs,
                                       const std::size_t lhsCols,
                                       const std::size_t rhsCols,
                                       const std::size_t column) {
  std::array<std::int8_t, 32> decoded{};
  std::int32_t sum = 0;
  std::size_t inner = 0;
  for (; inner + decoded.size() <= lhsCols; inner += decoded.size()) {
    for (std::size_t lane = 0; lane < decoded.size(); ++lane) {
      const std::size_t index = inner + lane;
      const std::uint8_t packed = packed_rhs[index * rhsCols + column / 2U];
      const std::uint8_t nibble = (column % 2U == 0U) ? (packed & 0x0FU)
                                                       : (packed >> 4U);
      decoded[lane] = static_cast<std::int8_t>(nibble) - 8;
    }
    sum += Avx2Dot(lhs + inner, decoded.data(), decoded.size());
  }
  for (; inner < lhsCols; ++inner) {
    const std::uint8_t packed = packed_rhs[inner * rhsCols + column / 2U];
    const std::uint8_t nibble = (column % 2U == 0U) ? (packed & 0x0FU)
                                                     : (packed >> 4U);
    sum += static_cast<std::int32_t>(lhs[inner]) *
           (static_cast<std::int32_t>(nibble) - 8);
  }
  return sum;
}
#endif

#if !US4_AVX2_TRANSLATION_UNIT
void ScalarPacked(const std::int8_t* lhs, const PackedInt8Matrix& packed,
                  const std::size_t lhsRows, const std::size_t lhsCols,
                  float* output) {
  if (lhs == nullptr || output == nullptr ||
      !ValidatePackedInt8Rhs(packed, lhsCols, packed.columns)) {
    return;
  }
  for (std::size_t row = 0; row < lhsRows; ++row) {
    for (std::size_t column = 0; column < packed.columns; ++column) {
      output[row * packed.columns + column] = static_cast<float>(ScalarDotPacked(
          lhs + row * lhsCols, packed, lhsCols, column));
    }
  }
}
#endif

}  // namespace

PackedInt8Matrix PackInt8Rhs(const std::int8_t* rhs, const std::size_t rows,
                             const std::size_t columns) {
  PackedInt8Matrix packed;
  packed.rows = rows;
  packed.columns = columns;
  if (rhs == nullptr) {
    packed.reason = "null source";
    return packed;
  }
  if (rows == 0U || columns == 0U) {
    packed.reason = "empty matrix";
    return packed;
  }
  packed.values.resize(rows * columns);
  for (std::size_t column = 0; column < columns; ++column) {
    for (std::size_t row = 0; row < rows; ++row) {
      packed.values[column * rows + row] = rhs[row * columns + column];
    }
  }
  packed.source_digest = Digest(rhs, rows * columns);
  packed.valid = true;
  packed.reason = "packed column-major for avx2";
  return packed;
}

bool ValidatePackedInt8Rhs(const PackedInt8Matrix& packed,
                           const std::size_t rows,
                           const std::size_t columns) {
  return packed.valid && packed.rows == rows && packed.columns == columns &&
         packed.values.size() == rows * columns &&
         !packed.source_digest.empty();
}

void Avx2Int8MatmulPacked(const std::int8_t* lhs,
                          const PackedInt8Matrix& packed,
                          const std::size_t lhsRows,
                          const std::size_t lhsCols, float* output) {
  if (lhs == nullptr || output == nullptr ||
      !ValidatePackedInt8Rhs(packed, lhsCols, packed.columns)) {
    return;
  }
#if US4_AVX2_TRANSLATION_UNIT
  RunAvx2Packed(lhs, packed, lhsRows, lhsCols, output);
#else
  ScalarPacked(lhs, packed, lhsRows, lhsCols, output);
#endif
}

void Avx2Int8Matmul(const std::int8_t* lhs, const std::int8_t* rhs,
                    const std::size_t lhsRows, const std::size_t lhsCols,
                    const std::size_t rhsCols, float* output) {
  const PackedInt8Matrix packed = PackInt8Rhs(rhs, lhsCols, rhsCols);
  if (!packed.valid) {
    ScalarMatmulRaw(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
    return;
  }
  Avx2Int8MatmulPacked(lhs, packed, lhsRows, lhsCols, output);
}

void Avx2Q4Matmul(const std::int8_t* lhs, const std::uint8_t* packed_rhs,
                  const float* scales, const std::size_t lhsRows,
                  const std::size_t lhsCols, const std::size_t rhsCols,
                  float* output) {
  if (lhs == nullptr || packed_rhs == nullptr || scales == nullptr ||
      output == nullptr || lhsCols == 0U || rhsCols == 0U) {
    return;
  }
  for (std::size_t row = 0; row < lhsRows; ++row) {
    for (std::size_t column = 0; column < rhsCols; ++column) {
      std::int32_t sum = 0;
#if US4_AVX2_TRANSLATION_UNIT
      sum = Avx2Q4Dot(lhs + row * lhsCols, packed_rhs, lhsCols, rhsCols,
                      column);
#else
      for (std::size_t inner = 0; inner < lhsCols; ++inner) {
        const std::uint8_t packed =
            packed_rhs[inner * rhsCols + column / 2U];
        const std::uint8_t nibble = (column % 2U == 0U) ? (packed & 0x0FU)
                                                         : (packed >> 4U);
        sum += static_cast<std::int32_t>(lhs[row * lhsCols + inner]) *
               (static_cast<std::int32_t>(nibble) - 8);
      }
#endif
      output[row * rhsCols + column] =
          static_cast<float>(sum) * scales[column];
    }
  }
}

void RegisterCpuInt8Kernels(KernelRegistry& registry) {
  KernelImplementation scalar;
  scalar.descriptor = {.name = "scalar",
                        .operation = KernelOperation::kInt8Matmul,
                        .dtype = "int8",
                        .isa_requirements = {},
                        .backend = "cpu",
                        .layout = "row-major",
                        .compiled = true,
                        .portable = true,
                        .priority = 0};
  scalar.int8_matmul = ScalarInt8Matmul;
  registry.Register(std::move(scalar));
#if US4_AVX2_TRANSLATION_UNIT
  KernelImplementation avx2;
  avx2.descriptor = {.name = "avx2",
                     .operation = KernelOperation::kInt8Matmul,
                     .dtype = "int8",
                     .isa_requirements = {"avx2"},
                     .backend = "cpu",
                     .layout = PackedInt8Matrix::kLayoutVersion,
                     .compiled = true,
                     .portable = false,
                     .priority = 20};
  avx2.int8_matmul = Avx2Int8Matmul;
  registry.Register(std::move(avx2));
#endif
}

}  // namespace us4
