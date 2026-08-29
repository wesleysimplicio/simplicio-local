#include "cpu/transformer_kernels.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <iterator>
#include <string_view>

#include "core/hardware_probe.h"

#if (defined(__x86_64__) || defined(_M_X64)) && \
    (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define US4_TRANSFORMER_AVX2 1
#else
#define US4_TRANSFORMER_AVX2 0
#endif

#if defined(__GNUC__) || defined(__clang__)
#define US4_TARGET_TRANSFORMER_AVX2 __attribute__((target("avx2")))
#else
#define US4_TARGET_TRANSFORMER_AVX2
#endif

namespace us4 {

namespace {

void FillReceipt(TransformerKernelReceipt* receipt, const char* operation,
                 const TransformerKernelKind selected) {
  if (receipt == nullptr) {
    return;
  }
  receipt->operation = operation;
  receipt->requested = selected;
  receipt->effective = selected;
  receipt->fallback = selected == TransformerKernelKind::kScalar;
  receipt->reason = receipt->fallback ? "portable scalar fallback"
                                      : "runtime ISA selected";
}

float SafeEpsilon(const float epsilon) {
  return std::isfinite(epsilon) && epsilon > 0.0F ? epsilon : 1e-5F;
}

void ScalarRmsNorm(const float* input, const std::size_t count, float* output,
                   const float epsilon) {
  long double sumSquares = 0.0L;
  for (std::size_t index = 0; index < count; ++index) {
    sumSquares += static_cast<long double>(input[index]) * input[index];
  }
  const float inverse = 1.0F / std::sqrt(
      static_cast<float>(sumSquares / static_cast<long double>(count)) + epsilon);
  for (std::size_t index = 0; index < count; ++index) {
    output[index] = input[index] * inverse;
  }
}

#if US4_TRANSFORMER_AVX2
US4_TARGET_TRANSFORMER_AVX2 void Avx2RmsNorm(
    const float* input, const std::size_t count, float* output,
    const float epsilon) {
  __m256 sum = _mm256_setzero_ps();
  std::size_t index = 0;
  for (; index + 8U <= count; index += 8U) {
    const __m256 values = _mm256_loadu_ps(input + index);
    sum = _mm256_add_ps(sum, _mm256_mul_ps(values, values));
  }
  alignas(32) float lanes[8] = {};
  _mm256_store_ps(lanes, sum);
  long double sumSquares = 0.0L;
  for (const float lane : lanes) {
    sumSquares += lane;
  }
  for (; index < count; ++index) {
    sumSquares += static_cast<long double>(input[index]) * input[index];
  }
  const float inverse = 1.0F / std::sqrt(
      static_cast<float>(sumSquares / static_cast<long double>(count)) + epsilon);
  const __m256 inverseVector = _mm256_set1_ps(inverse);
  index = 0;
  for (; index + 8U <= count; index += 8U) {
    _mm256_storeu_ps(output + index,
                     _mm256_mul_ps(_mm256_loadu_ps(input + index), inverseVector));
  }
  for (; index < count; ++index) {
    output[index] = input[index] * inverse;
  }
}

US4_TARGET_TRANSFORMER_AVX2 float Avx2Max(const float* values,
                                          const std::size_t count,
                                          const std::uint8_t* mask) {
  __m256 maximum = _mm256_set1_ps(-std::numeric_limits<float>::infinity());
  std::size_t index = 0;
  for (; index + 8U <= count; index += 8U) {
    float lanes[8];
    for (std::size_t lane = 0; lane < 8U; ++lane) {
      lanes[lane] = mask == nullptr || mask[index + lane]
                        ? values[index + lane]
                        : -std::numeric_limits<float>::infinity();
    }
    maximum = _mm256_max_ps(maximum, _mm256_loadu_ps(lanes));
  }
  alignas(32) float lanes[8] = {};
  _mm256_store_ps(lanes, maximum);
  float result = *std::max_element(std::begin(lanes), std::end(lanes));
  for (; index < count; ++index) {
    if (mask == nullptr || mask[index]) {
      result = std::max(result, values[index]);
    }
  }
  return result;
}
#endif

}  // namespace

std::string_view ToString(const TransformerKernelKind kind) {
  switch (kind) {
    case TransformerKernelKind::kScalar:
      return "scalar";
    case TransformerKernelKind::kAvx2:
      return "avx2";
    case TransformerKernelKind::kNeon:
      return "neon";
  }
  return "scalar";
}

TransformerKernelKind SelectTransformerKernel(const bool avx2, const bool neon) {
  if (avx2) {
    return TransformerKernelKind::kAvx2;
  }
  if (neon) {
    return TransformerKernelKind::kNeon;
  }
  return TransformerKernelKind::kScalar;
}

bool RmsNorm(const float* input, const std::size_t count, float* output,
             const float epsilon, TransformerKernelReceipt* receipt) {
  if (input == nullptr || output == nullptr || count == 0U) {
    return false;
  }
  const HardwareProbeResult hardware = HardwareProbe::Detect();
  const TransformerKernelKind selected =
      SelectTransformerKernel(hardware.hasAvx2, hardware.hasNeon);
  FillReceipt(receipt, "rmsnorm", selected);
#if US4_TRANSFORMER_AVX2
  if (selected == TransformerKernelKind::kAvx2) {
    Avx2RmsNorm(input, count, output, SafeEpsilon(epsilon));
    return true;
  }
#endif
  ScalarRmsNorm(input, count, output, SafeEpsilon(epsilon));
  return true;
}

bool Softmax(float* values, const std::size_t count, const std::uint8_t* mask,
             TransformerKernelReceipt* receipt) {
  if (values == nullptr || count == 0U) {
    return false;
  }
  const HardwareProbeResult hardware = HardwareProbe::Detect();
  const TransformerKernelKind selected =
      SelectTransformerKernel(hardware.hasAvx2, hardware.hasNeon);
  FillReceipt(receipt, "softmax", selected);
  float maximum = -std::numeric_limits<float>::infinity();
  for (std::size_t index = 0; index < count; ++index) {
    if ((mask == nullptr || mask[index]) && std::isnan(values[index])) {
      return false;
    }
  }
#if US4_TRANSFORMER_AVX2
  if (selected == TransformerKernelKind::kAvx2) {
    maximum = Avx2Max(values, count, mask);
  } else
#endif
  {
    for (std::size_t index = 0; index < count; ++index) {
      if (mask == nullptr || mask[index]) {
        maximum = std::max(maximum, values[index]);
      }
    }
  }
  std::size_t positiveInfinityCount = 0U;
  for (std::size_t index = 0; index < count; ++index) {
    if ((mask == nullptr || mask[index]) &&
        values[index] == std::numeric_limits<float>::infinity()) {
      ++positiveInfinityCount;
    }
  }
  if (positiveInfinityCount != 0U) {
    const float probability = 1.0F / static_cast<float>(positiveInfinityCount);
    for (std::size_t index = 0; index < count; ++index) {
      values[index] = (mask == nullptr || mask[index]) &&
                              values[index] == std::numeric_limits<float>::infinity()
                          ? probability
                          : 0.0F;
    }
    return true;
  }
  if (!std::isfinite(maximum)) {
    std::fill(values, values + count, 0.0F);
    return true;
  }
  double sum = 0.0;
  for (std::size_t index = 0; index < count; ++index) {
    if (mask != nullptr && mask[index] == 0U) {
      values[index] = 0.0F;
      continue;
    }
    values[index] = std::exp(values[index] - maximum);
    sum += values[index];
  }
  if (!(sum > 0.0) || !std::isfinite(sum)) {
    return false;
  }
  const float inverse = static_cast<float>(1.0 / sum);
  for (std::size_t index = 0; index < count; ++index) {
    if (mask == nullptr || mask[index]) {
      values[index] *= inverse;
    }
  }
  return true;
}

void ApplySilu(float* values, const std::size_t count,
               TransformerKernelReceipt* receipt) {
  if (values == nullptr || count == 0U) {
    return;
  }
  const HardwareProbeResult hardware = HardwareProbe::Detect();
  const TransformerKernelKind selected =
      SelectTransformerKernel(hardware.hasAvx2, hardware.hasNeon);
  FillReceipt(receipt, "silu", selected);
  for (std::size_t index = 0; index < count; ++index) {
    const float value = values[index];
    if (std::isnan(value) || value == std::numeric_limits<float>::infinity()) {
      values[index] = value;
    } else if (value == -std::numeric_limits<float>::infinity()) {
      values[index] = 0.0F;
    } else {
      values[index] = value / (1.0F + std::exp(-value));
    }
  }
}

bool ApplyRope(float* query, float* key, const std::size_t sequence_count,
               const std::size_t head_dim, const std::size_t position,
               const float theta, TransformerKernelReceipt* receipt) {
  if (head_dim < 2U || (query == nullptr && key == nullptr) ||
      !std::isfinite(theta) || theta <= 0.0F) {
    return false;
  }
  const HardwareProbeResult hardware = HardwareProbe::Detect();
  const TransformerKernelKind selected =
      SelectTransformerKernel(hardware.hasAvx2, hardware.hasNeon);
  FillReceipt(receipt, "rope", selected);
  const std::size_t pairs = head_dim / 2U;
  for (std::size_t sequence = 0; sequence < sequence_count; ++sequence) {
    for (std::size_t pair = 0; pair < pairs; ++pair) {
      const float angle = static_cast<float>(position + sequence) *
                          std::pow(theta, -2.0F * static_cast<float>(pair) /
                                            static_cast<float>(head_dim));
      const float cosine = std::cos(angle);
      const float sine = std::sin(angle);
      const std::size_t offset = sequence * head_dim + pair * 2U;
      if (query != nullptr) {
        const float first = query[offset];
        const float second = query[offset + 1U];
        query[offset] = first * cosine - second * sine;
        query[offset + 1U] = first * sine + second * cosine;
      }
      if (key != nullptr) {
        const float first = key[offset];
        const float second = key[offset + 1U];
        key[offset] = first * cosine - second * sine;
        key[offset + 1U] = first * sine + second * cosine;
      }
    }
  }
  return true;
}

}  // namespace us4
