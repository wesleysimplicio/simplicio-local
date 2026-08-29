#include "cpu/avx512_kernels.h"

#include <array>
#include <cstdint>

#include "cpu/avx2_kernels.h"

#if (defined(__x86_64__) || defined(_M_X64)) && \
    (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define US4_AVX512_TRANSLATION_UNIT 1
#else
#define US4_AVX512_TRANSLATION_UNIT 0
#endif

#if defined(__GNUC__) || defined(__clang__)
#define US4_TARGET_AVX512 \
  __attribute__((target("avx512f,avx512bw,avx512vnni")))
#else
#define US4_TARGET_AVX512
#endif

namespace us4 {

namespace {

void ScalarMatmul(const std::int8_t* lhs, const std::int8_t* rhs,
                  const std::size_t lhsRows, const std::size_t lhsCols,
                  const std::size_t rhsCols, float* output) {
  if (lhs == nullptr || rhs == nullptr || output == nullptr) {
    return;
  }
  for (std::size_t row = 0; row < lhsRows; ++row) {
    for (std::size_t column = 0; column < rhsCols; ++column) {
      std::int32_t sum = 0;
      for (std::size_t inner = 0; inner < lhsCols; ++inner) {
        sum += static_cast<std::int32_t>(lhs[row * lhsCols + inner]) *
               static_cast<std::int32_t>(rhs[inner * rhsCols + column]);
      }
      output[row * rhsCols + column] = static_cast<float>(sum);
    }
  }
}

#if US4_AVX512_TRANSLATION_UNIT
US4_TARGET_AVX512 std::int32_t Dot(const std::int8_t* lhs,
                                   const std::int8_t* rhs,
                                   const std::size_t count) {
  __m512i accumulator = _mm512_setzero_si512();
  std::size_t index = 0;
  for (; index + 32U <= count; index += 32U) {
    const __m256i lhs8 = _mm256_loadu_si256(
        reinterpret_cast<const __m256i*>(lhs + index));
    const __m256i rhs8 = _mm256_loadu_si256(
        reinterpret_cast<const __m256i*>(rhs + index));
    const __m512i lhs16 = _mm512_cvtepi8_epi16(lhs8);
    const __m512i rhs16 = _mm512_cvtepi8_epi16(rhs8);
    // VNNI's dpwssd computes adjacent signed-int16 products and accumulates
    // them into signed-int32 lanes. This handles the full int8 range without
    // the unsigned/signed asymmetry of dpbusd.
    accumulator = _mm512_dpwssd_epi32(accumulator, lhs16, rhs16);
  }
  alignas(64) std::array<std::int32_t, 16> lanes{};
  _mm512_store_si512(reinterpret_cast<void*>(lanes.data()), accumulator);
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

US4_TARGET_AVX512 void RunPacked(const std::int8_t* lhs,
                                 const PackedInt8Matrix& packed,
                                 const std::size_t lhsRows,
                                 const std::size_t lhsCols, float* output) {
  for (std::size_t row = 0; row < lhsRows; ++row) {
    for (std::size_t column = 0; column < packed.columns; ++column) {
      const auto* rhsColumn = packed.values.data() + column * packed.rows;
      output[row * packed.columns + column] = static_cast<float>(
          Dot(lhs + row * lhsCols, rhsColumn, lhsCols));
    }
  }
}
#endif

}  // namespace

void Avx512VnniInt8Matmul(const std::int8_t* lhs, const std::int8_t* rhs,
                          const std::size_t lhsRows,
                          const std::size_t lhsCols,
                          const std::size_t rhsCols, float* output) {
  if (lhs == nullptr || rhs == nullptr || output == nullptr) {
    return;
  }
#if US4_AVX512_TRANSLATION_UNIT
  const PackedInt8Matrix packed = PackInt8Rhs(rhs, lhsCols, rhsCols);
  if (packed.valid) {
    RunPacked(lhs, packed, lhsRows, lhsCols, output);
    return;
  }
#endif
  ScalarMatmul(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
}

}  // namespace us4
