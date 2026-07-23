#pragma once

#include <string>

#include "core/tensor.h"
#include "cpu/int8_matmul.h"

namespace us4 {

bool NeonMatmul(const Tensor &lhs, const Tensor &rhs, Tensor &output,
                std::string *error = nullptr,
                CpuInt8Dispatch *int8Dispatch = nullptr);

}  // namespace us4
