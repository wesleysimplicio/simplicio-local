#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "core/tensor.h"
#include "neon/dequant_int8.h"

// Quantization-kernel fuzz target (issue #145). The oracle is deliberately
// scalar and independent from the production loop: a memory-safe execution
// is not enough if a future SIMD implementation changes the decoded values.
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data,
                                      const std::size_t size) {
  if (data == nullptr || size == 0) {
    return 0;
  }

  const std::size_t elementCount = std::min<std::size_t>(size, 4096U);
  const std::size_t groupSize = 1U + (data[0] % 64U);
  us4::Tensor quantized({elementCount}, us4::DType::kInt8);
  auto *encoded = reinterpret_cast<std::int8_t *>(quantized.MutableData());
  std::vector<float> scales(
      (elementCount + groupSize - 1U) / groupSize, 1.0F);
  for (std::size_t index = 0; index < elementCount; ++index) {
    encoded[index] = static_cast<std::int8_t>(data[index] ^ 0x80U);
    scales[index / groupSize] =
        0.0625F + static_cast<float>(data[index] & 0x7FU) / 32.0F;
  }

  us4::Tensor output({elementCount}, us4::DType::kFloat32);
  std::string error;
  if (!us4::DequantizeInt8Groups(quantized, groupSize, scales, output,
                                 &error)) {
    return 0;
  }
  const float *decoded = output.DataAsFloat32();
  for (std::size_t index = 0; index < elementCount; ++index) {
    const float expected = static_cast<float>(encoded[index]) *
                           scales[index / groupSize];
    if (!std::isfinite(decoded[index]) || decoded[index] != expected) {
      __builtin_trap();
    }
  }
  return 0;
}
