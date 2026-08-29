#pragma once

#include <cstddef>
#include <string>
#include <string_view>

#include "core/tensor.h"

namespace us4 {

enum class FloatKernelKind {
  kScalar,
  kAvx2,
  kNeon,
};

std::string_view ToString(FloatKernelKind kind);

struct FloatKernelDispatch {
  FloatKernelKind kind = FloatKernelKind::kScalar;
  bool accelerated = false;
  bool fallback = true;
  std::string reason = "portable scalar fallback";
};

FloatKernelDispatch SelectFloatKernel(bool avx2, bool neon);

bool CpuFloatMatmul(const Tensor& lhs, const Tensor& rhs, Tensor& output,
                    FloatKernelDispatch* dispatch = nullptr,
                    std::string* error = nullptr);

}  // namespace us4
