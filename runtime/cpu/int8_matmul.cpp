#include "cpu/int8_matmul.h"

#include <array>
#include <cstdint>

#if defined(__ARM_NEON) || defined(__ARM_NEON__)
#include <arm_neon.h>
#endif

#if (defined(__x86_64__) || defined(_M_X64)) &&                           \
    (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define US4_HAS_X86_VNNI_KERNEL 1
#else
#define US4_HAS_X86_VNNI_KERNEL 0
#endif

namespace us4 {

namespace {

std::int32_t ScalarDot(const std::int8_t *lhs, const std::int8_t *rhs,
                       const std::size_t rhsCols, const std::size_t column,
                       const std::size_t innerBegin,
                       const std::size_t innerEnd) {
  std::int32_t accumulator = 0;
  for (std::size_t inner = innerBegin; inner < innerEnd; ++inner) {
    accumulator +=
        static_cast<std::int32_t>(lhs[inner]) *
        static_cast<std::int32_t>(rhs[inner * rhsCols + column]);
  }
  return accumulator;
}

void RunScalar(const std::int8_t *lhs, const std::int8_t *rhs,
               const std::size_t lhsRows, const std::size_t lhsCols,
               const std::size_t rhsCols, float *output) {
  for (std::size_t row = 0; row < lhsRows; ++row) {
    const std::int8_t *lhsRow = lhs + row * lhsCols;
    for (std::size_t column = 0; column < rhsCols; ++column) {
      output[row * rhsCols + column] =
          static_cast<float>(ScalarDot(lhsRow, rhs, rhsCols, column, 0U,
                                       lhsCols));
    }
  }
}

#if defined(__ARM_NEON) && defined(__ARM_FEATURE_DOTPROD)
std::int32_t NeonSdot(const std::int8_t *lhs, const std::int8_t *rhs,
                      const std::size_t lhsCols, const std::size_t rhsCols,
                      const std::size_t column) {
  int32x4_t accumulator = vdupq_n_s32(0);
  std::size_t inner = 0;
  for (; inner + 16U <= lhsCols; inner += 16U) {
    std::array<std::int8_t, 16> packedRhs{};
    for (std::size_t lane = 0; lane < packedRhs.size(); ++lane) {
      packedRhs[lane] = rhs[(inner + lane) * rhsCols + column];
    }
    accumulator =
        vdotq_s32(accumulator, vld1q_s8(lhs + inner),
                  vld1q_s8(packedRhs.data()));
  }
  const std::int32_t vectorSum = vaddvq_s32(accumulator);
  return vectorSum +
         ScalarDot(lhs, rhs, rhsCols, column, inner, lhsCols);
}

void RunNeonSdot(const std::int8_t *lhs, const std::int8_t *rhs,
                 const std::size_t lhsRows, const std::size_t lhsCols,
                 const std::size_t rhsCols, float *output) {
  for (std::size_t row = 0; row < lhsRows; ++row) {
    const std::int8_t *lhsRow = lhs + row * lhsCols;
    for (std::size_t column = 0; column < rhsCols; ++column) {
      output[row * rhsCols + column] = static_cast<float>(
          NeonSdot(lhsRow, rhs, lhsCols, rhsCols, column));
    }
  }
}
#endif

#if defined(__ARM_NEON) && defined(__ARM_FEATURE_MATMUL_INT8)
void RunNeonI8mm(const std::int8_t *lhs, const std::int8_t *rhs,
                 const std::size_t lhsRows, const std::size_t lhsCols,
                 const std::size_t rhsCols, float *output) {
  std::size_t row = 0;
  for (; row + 2U <= lhsRows; row += 2U) {
    std::size_t column = 0;
    for (; column + 2U <= rhsCols; column += 2U) {
      int32x4_t accumulator = vdupq_n_s32(0);
      std::size_t inner = 0;
      for (; inner + 8U <= lhsCols; inner += 8U) {
        std::array<std::int8_t, 16> packedLhs{};
        std::array<std::int8_t, 16> packedRhs{};
        for (std::size_t lane = 0; lane < 8U; ++lane) {
          packedLhs[lane] = lhs[row * lhsCols + inner + lane];
          packedLhs[8U + lane] =
              lhs[(row + 1U) * lhsCols + inner + lane];
          packedRhs[2U * lane] =
              rhs[(inner + lane) * rhsCols + column];
          packedRhs[2U * lane + 1U] =
              rhs[(inner + lane) * rhsCols + column + 1U];
        }
        accumulator =
            vmmlaq_s32(accumulator, vld1q_s8(packedLhs.data()),
                       vld1q_s8(packedRhs.data()));
      }

      std::array<std::int32_t, 4> sums{};
      vst1q_s32(sums.data(), accumulator);
      const std::int8_t *lhsRow0 = lhs + row * lhsCols;
      const std::int8_t *lhsRow1 = lhs + (row + 1U) * lhsCols;
      sums[0] += ScalarDot(lhsRow0, rhs, rhsCols, column, inner, lhsCols);
      sums[1] +=
          ScalarDot(lhsRow0, rhs, rhsCols, column + 1U, inner, lhsCols);
      sums[2] += ScalarDot(lhsRow1, rhs, rhsCols, column, inner, lhsCols);
      sums[3] +=
          ScalarDot(lhsRow1, rhs, rhsCols, column + 1U, inner, lhsCols);
      output[row * rhsCols + column] = static_cast<float>(sums[0]);
      output[row * rhsCols + column + 1U] = static_cast<float>(sums[1]);
      output[(row + 1U) * rhsCols + column] =
          static_cast<float>(sums[2]);
      output[(row + 1U) * rhsCols + column + 1U] =
          static_cast<float>(sums[3]);
    }

    for (; column < rhsCols; ++column) {
      output[row * rhsCols + column] = static_cast<float>(ScalarDot(
          lhs + row * lhsCols, rhs, rhsCols, column, 0U, lhsCols));
      output[(row + 1U) * rhsCols + column] =
          static_cast<float>(ScalarDot(lhs + (row + 1U) * lhsCols, rhs,
                                       rhsCols, column, 0U, lhsCols));
    }
  }

  if (row < lhsRows) {
    const std::int8_t *lhsRow = lhs + row * lhsCols;
    for (std::size_t column = 0; column < rhsCols; ++column) {
      output[row * rhsCols + column] = static_cast<float>(
          ScalarDot(lhsRow, rhs, rhsCols, column, 0U, lhsCols));
    }
  }
}
#endif

#if US4_HAS_X86_VNNI_KERNEL
__attribute__((target("avx512f,avx512bw,avx512vnni")))
std::int32_t X86VnniDot(const std::int8_t *lhs, const std::int8_t *rhs,
                        const std::size_t lhsCols,
                        const std::size_t rhsCols,
                        const std::size_t column) {
  __m512i accumulator = _mm512_setzero_si512();
  std::size_t inner = 0;
  for (; inner + 32U <= lhsCols; inner += 32U) {
    std::array<std::int8_t, 32> packedRhs{};
    for (std::size_t lane = 0; lane < packedRhs.size(); ++lane) {
      packedRhs[lane] = rhs[(inner + lane) * rhsCols + column];
    }
    const __m256i lhs8 = _mm256_loadu_si256(
        reinterpret_cast<const __m256i *>(lhs + inner));
    const __m256i rhs8 = _mm256_loadu_si256(
        reinterpret_cast<const __m256i *>(packedRhs.data()));
    accumulator =
        _mm512_dpwssd_epi32(accumulator, _mm512_cvtepi8_epi16(lhs8),
                            _mm512_cvtepi8_epi16(rhs8));
  }

  std::array<std::int32_t, 16> lanes{};
  _mm512_storeu_si512(lanes.data(), accumulator);
  std::int32_t result = 0;
  for (const std::int32_t lane : lanes) {
    result += lane;
  }
  return result + ScalarDot(lhs, rhs, rhsCols, column, inner, lhsCols);
}

__attribute__((target("avx512f,avx512bw,avx512vnni")))
void RunX86Vnni(const std::int8_t *lhs, const std::int8_t *rhs,
                const std::size_t lhsRows, const std::size_t lhsCols,
                const std::size_t rhsCols, float *output) {
  for (std::size_t row = 0; row < lhsRows; ++row) {
    const std::int8_t *lhsRow = lhs + row * lhsCols;
    for (std::size_t column = 0; column < rhsCols; ++column) {
      output[row * rhsCols + column] = static_cast<float>(
          X86VnniDot(lhsRow, rhs, lhsCols, rhsCols, column));
    }
  }
}
#endif

} // namespace

std::string_view ToString(const CpuInt8Kernel kernel) {
  switch (kernel) {
  case CpuInt8Kernel::kScalar:
    return "scalar";
  case CpuInt8Kernel::kNeonSdot:
    return "neon-sdot";
  case CpuInt8Kernel::kNeonI8mm:
    return "neon-i8mm";
  case CpuInt8Kernel::kX86Vnni:
    return "x86-vnni";
  }
  return "scalar";
}

CpuInt8Capabilities DetectCpuInt8Capabilities() {
  CpuInt8Capabilities capabilities;
#if defined(__ARM_NEON) && defined(__ARM_FEATURE_DOTPROD)
  capabilities.neonSdot = true;
#endif
#if defined(__ARM_NEON) && defined(__ARM_FEATURE_MATMUL_INT8)
  capabilities.neonI8mm = true;
#endif
#if US4_HAS_X86_VNNI_KERNEL
  __builtin_cpu_init();
  capabilities.x86Vnni =
      __builtin_cpu_supports("avx512f") &&
      __builtin_cpu_supports("avx512bw") &&
      __builtin_cpu_supports("avx512vnni");
#endif
  return capabilities;
}

CpuInt8Dispatch
SelectCpuInt8Kernel(const CpuInt8Capabilities &capabilities) {
  if (capabilities.neonI8mm) {
    return {.kernel = CpuInt8Kernel::kNeonI8mm, .accelerated = true};
  }
  if (capabilities.neonSdot) {
    return {.kernel = CpuInt8Kernel::kNeonSdot, .accelerated = true};
  }
  if (capabilities.x86Vnni) {
    return {.kernel = CpuInt8Kernel::kX86Vnni, .accelerated = true};
  }
  return {};
}

CpuInt8Dispatch SelectCpuInt8Kernel() {
  static const CpuInt8Dispatch dispatch =
      SelectCpuInt8Kernel(DetectCpuInt8Capabilities());
  return dispatch;
}

void ScalarInt8Matmul(const std::int8_t *lhs, const std::int8_t *rhs,
                      const std::size_t lhsRows, const std::size_t lhsCols,
                      const std::size_t rhsCols, float *output) {
  RunScalar(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
}

void CpuInt8Matmul(const std::int8_t *lhs, const std::int8_t *rhs,
                   const std::size_t lhsRows, const std::size_t lhsCols,
                   const std::size_t rhsCols, float *output,
                   CpuInt8Dispatch *dispatch) {
  const CpuInt8Dispatch selected = SelectCpuInt8Kernel();
  if (dispatch != nullptr) {
    *dispatch = selected;
  }

  switch (selected.kernel) {
#if defined(__ARM_NEON) && defined(__ARM_FEATURE_MATMUL_INT8)
  case CpuInt8Kernel::kNeonI8mm:
    RunNeonI8mm(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
    return;
#endif
#if defined(__ARM_NEON) && defined(__ARM_FEATURE_DOTPROD)
  case CpuInt8Kernel::kNeonSdot:
    RunNeonSdot(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
    return;
#endif
#if US4_HAS_X86_VNNI_KERNEL
  case CpuInt8Kernel::kX86Vnni:
    RunX86Vnni(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
    return;
#endif
  case CpuInt8Kernel::kScalar:
  default:
    ScalarInt8Matmul(lhs, rhs, lhsRows, lhsCols, rhsCols, output);
    return;
  }
}

} // namespace us4
