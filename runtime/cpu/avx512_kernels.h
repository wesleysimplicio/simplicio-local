#pragma once

#include <cstddef>
#include <cstdint>

namespace us4 {

// This entry point is baseline-safe. The AVX-512 implementation is isolated
// in its own target-attributed translation unit and falls back to the scalar
// algorithm when the compiler cannot emit the specialized code.
void Avx512VnniInt8Matmul(const std::int8_t* lhs, const std::int8_t* rhs,
                          std::size_t lhsRows, std::size_t lhsCols,
                          std::size_t rhsCols, float* output);

}  // namespace us4
