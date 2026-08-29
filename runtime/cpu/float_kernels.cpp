#include "cpu/float_kernels.h"

#include <cstddef>
#include <string_view>

#include "core/hardware_probe.h"

#if (defined(__x86_64__) || defined(_M_X64)) && \
    (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define US4_FLOAT_AVX2 1
#else
#define US4_FLOAT_AVX2 0
#endif

#if defined(__GNUC__) || defined(__clang__)
#define US4_TARGET_FLOAT_AVX2 __attribute__((target("avx2")))
#else
#define US4_TARGET_FLOAT_AVX2
#endif

namespace us4 {

namespace {

bool WriteError(std::string* error, const char* message) {
  if (error != nullptr) {
    *error = message;
  }
  return false;
}

bool IsFloatDType(const DType dtype) {
  return dtype == DType::kFloat32 || dtype == DType::kFloat16 ||
         dtype == DType::kBFloat16;
}

bool Validate(const Tensor& tensor, std::string* error) {
  if (!IsFloatDType(tensor.dtype())) {
    return WriteError(error, "tensor must be fp32, fp16 or bf16");
  }
  if (tensor.Rank() != 2 || !tensor.IsContiguous()) {
    return WriteError(error, "tensor must be a contiguous rank-2 matrix");
  }
  if (tensor.Data() == nullptr) {
    return WriteError(error, "tensor storage is unavailable");
  }
  return true;
}

float Read(const Tensor& tensor, const std::size_t index) {
  if (tensor.dtype() == DType::kFloat32) {
    return tensor.DataAsFloat32()[index];
  }
  if (tensor.dtype() == DType::kFloat16) {
    return DecodeFloat16(tensor.DataAsUInt16()[index]);
  }
  return DecodeBFloat16(tensor.DataAsUInt16()[index]);
}

void RunScalar(const Tensor& lhs, const Tensor& rhs, Tensor& output) {
  const std::size_t rows = lhs.Shape()[0];
  const std::size_t inner = lhs.Shape()[1];
  const std::size_t columns = rhs.Shape()[1];
  float* outputData = output.MutableDataAsFloat32();
  for (std::size_t row = 0; row < rows; ++row) {
    for (std::size_t column = 0; column < columns; ++column) {
      float sum = 0.0F;
      for (std::size_t index = 0; index < inner; ++index) {
        sum += Read(lhs, row * inner + index) *
               Read(rhs, index * columns + column);
      }
      outputData[row * columns + column] = sum;
    }
  }
}

#if US4_FLOAT_AVX2
US4_TARGET_FLOAT_AVX2 void RunAvx2(const Tensor& lhs, const Tensor& rhs,
                                    Tensor& output) {
  const std::size_t rows = lhs.Shape()[0];
  const std::size_t inner = lhs.Shape()[1];
  const std::size_t columns = rhs.Shape()[1];
  float* outputData = output.MutableDataAsFloat32();
  constexpr std::size_t kLanes = 8U;
  for (std::size_t row = 0; row < rows; ++row) {
    std::size_t column = 0;
    for (; column + kLanes <= columns; column += kLanes) {
      __m256 accumulator = _mm256_setzero_ps();
      for (std::size_t index = 0; index < inner; ++index) {
        const float rhsValues[kLanes] = {
            Read(rhs, index * columns + column + 0U),
            Read(rhs, index * columns + column + 1U),
            Read(rhs, index * columns + column + 2U),
            Read(rhs, index * columns + column + 3U),
            Read(rhs, index * columns + column + 4U),
            Read(rhs, index * columns + column + 5U),
            Read(rhs, index * columns + column + 6U),
            Read(rhs, index * columns + column + 7U)};
        const __m256 values = _mm256_loadu_ps(rhsValues);
        accumulator = _mm256_add_ps(
            accumulator,
            _mm256_mul_ps(values, _mm256_set1_ps(Read(lhs, row * inner + index))));
      }
      _mm256_storeu_ps(outputData + row * columns + column, accumulator);
    }
    for (; column < columns; ++column) {
      float sum = 0.0F;
      for (std::size_t index = 0; index < inner; ++index) {
        sum += Read(lhs, row * inner + index) *
               Read(rhs, index * columns + column);
      }
      outputData[row * columns + column] = sum;
    }
  }
}
#endif

}  // namespace

std::string_view ToString(const FloatKernelKind kind) {
  switch (kind) {
    case FloatKernelKind::kScalar:
      return "scalar";
    case FloatKernelKind::kAvx2:
      return "avx2";
    case FloatKernelKind::kNeon:
      return "neon";
  }
  return "scalar";
}

FloatKernelDispatch SelectFloatKernel(const bool avx2, const bool neon) {
  if (avx2) {
    return {.kind = FloatKernelKind::kAvx2,
            .accelerated = true,
            .fallback = false,
            .reason = "runtime AVX2 capability"};
  }
  if (neon) {
    return {.kind = FloatKernelKind::kNeon,
            .accelerated = true,
            .fallback = false,
            .reason = "runtime NEON capability"};
  }
  return {};
}

bool CpuFloatMatmul(const Tensor& lhs, const Tensor& rhs, Tensor& output,
                    FloatKernelDispatch* dispatch, std::string* error) {
  if (!Validate(lhs, error) || !Validate(rhs, error)) {
    return false;
  }
  if (lhs.dtype() != rhs.dtype()) {
    return WriteError(error, "lhs and rhs dtypes must match");
  }
  if (output.dtype() != DType::kFloat32 || output.Rank() != 2 ||
      !output.IsContiguous() || output.MutableDataAsFloat32() == nullptr) {
    return WriteError(error, "output must be a writable contiguous fp32 matrix");
  }
  if (lhs.Shape()[1] != rhs.Shape()[0] || output.Shape()[0] != lhs.Shape()[0] ||
      output.Shape()[1] != rhs.Shape()[1]) {
    return WriteError(error, "matrix shapes are incompatible");
  }

  const HardwareProbeResult hardware = HardwareProbe::Detect();
  FloatKernelDispatch selected = SelectFloatKernel(
      hardware.hasAvx2, hardware.hasNeon);
  if (selected.kind == FloatKernelKind::kAvx2) {
#if US4_FLOAT_AVX2
    RunAvx2(lhs, rhs, output);
#else
    selected = {};
    RunScalar(lhs, rhs, output);
#endif
  } else {
    // The NEON implementation remains owned by neon/neon_matmul.cpp; this
    // generic entry point stays correct when called on an ARM host without
    // that optional translation unit.
    RunScalar(lhs, rhs, output);
  }
  if (dispatch != nullptr) {
    *dispatch = selected;
  }
  return true;
}

}  // namespace us4
