#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace us4 {

enum class TransformerKernelKind {
  kScalar,
  kAvx2,
  kNeon,
};

std::string_view ToString(TransformerKernelKind kind);

struct TransformerKernelReceipt {
  std::string operation;
  TransformerKernelKind requested = TransformerKernelKind::kScalar;
  TransformerKernelKind effective = TransformerKernelKind::kScalar;
  bool fallback = true;
  std::string reason = "portable scalar fallback";
};

TransformerKernelKind SelectTransformerKernel(bool avx2, bool neon);

bool RmsNorm(const float* input, std::size_t count, float* output,
             float epsilon = 1e-5F,
             TransformerKernelReceipt* receipt = nullptr);

// `mask` is optional. When provided, a zero entry is masked and a non-zero
// entry participates in the stable max/exp/sum reduction. An all-masked row
// is filled with zeros.
bool Softmax(float* values, std::size_t count, const std::uint8_t* mask = nullptr,
             TransformerKernelReceipt* receipt = nullptr);

void ApplySilu(float* values, std::size_t count,
               TransformerKernelReceipt* receipt = nullptr);

// Rotate query/key in place. The final odd head-dimension element, when any,
// is deliberately preserved instead of being read out of bounds.
bool ApplyRope(float* query, float* key, std::size_t sequence_count,
               std::size_t head_dim, std::size_t position,
               float theta = 10000.0F,
               TransformerKernelReceipt* receipt = nullptr);

}  // namespace us4
