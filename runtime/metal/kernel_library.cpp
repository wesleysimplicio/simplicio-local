#include "metal/kernel_library.h"

namespace us4 {

namespace {

constexpr std::string_view kMatmulSource = R"(#include <metal_stdlib>
using namespace metal;

kernel void us4_matmul_fp32(
    device const float* lhs [[buffer(0)]],
    device const float* rhs [[buffer(1)]],
    device float* out [[buffer(2)]],
    constant uint& inner [[buffer(3)]],
    constant uint& width [[buffer(4)]],
    uint gid [[thread_position_in_grid]]) {
  const uint row = gid / width;
  const uint col = gid % width;
  float value = 0.0f;
  for (uint k = 0; k < inner; ++k) {
    value += lhs[row * inner + k] * rhs[k * width + col];
  }
  out[gid] = value;
}
)";

constexpr std::string_view kSoftmaxSource = R"(#include <metal_stdlib>
using namespace metal;

kernel void us4_softmax_rows(
    device const float* input [[buffer(0)]],
    device float* output [[buffer(1)]],
    constant uint& width [[buffer(2)]],
    uint gid [[thread_position_in_grid]]) {
  const uint row = gid / width;
  const uint col = gid % width;
  const uint rowBase = row * width;
  float maxValue = input[rowBase];
  for (uint i = 1; i < width; ++i) {
    maxValue = max(maxValue, input[rowBase + i]);
  }
  float denom = 0.0f;
  for (uint i = 0; i < width; ++i) {
    denom += exp(input[rowBase + i] - maxValue);
  }
  output[gid] = exp(input[rowBase + col] - maxValue) / max(denom, 1e-6f);
}
)";

constexpr std::string_view kRmsNormSource = R"(#include <metal_stdlib>
using namespace metal;

kernel void us4_rmsnorm_fp32(
    device const float* input [[buffer(0)]],
    device const float* weight [[buffer(1)]],
    device float* output [[buffer(2)]],
    constant uint& width [[buffer(3)]],
    uint gid [[thread_position_in_grid]]) {
  const uint row = gid / width;
  const uint col = gid % width;
  const uint rowBase = row * width;
  float sumSquares = 0.0f;
  for (uint i = 0; i < width; ++i) {
    const float v = input[rowBase + i];
    sumSquares += v * v;
  }
  const float invRms = rsqrt(max(sumSquares / max(float(width), 1.0f), 1e-6f));
  output[gid] = input[rowBase + col] * invRms * weight[col];
}
)";

constexpr MetalKernelCatalog kCatalog = {{
    {
        .kind = MetalKernelKind::kMatmul,
        .entryPoint = "us4_matmul_fp32",
        .relativePath = "runtime/metal/kernels/matmul.metal",
        .source = kMatmulSource,
        .preferredThreadsPerGroup = 32,
    },
    {
        .kind = MetalKernelKind::kSoftmax,
        .entryPoint = "us4_softmax_rows",
        .relativePath = "runtime/metal/kernels/softmax.metal",
        .source = kSoftmaxSource,
        .preferredThreadsPerGroup = 64,
    },
    {
        .kind = MetalKernelKind::kRmsNorm,
        .entryPoint = "us4_rmsnorm_fp32",
        .relativePath = "runtime/metal/kernels/rmsnorm.metal",
        .source = kRmsNormSource,
        .preferredThreadsPerGroup = 64,
    },
}};

}  // namespace

const MetalKernelCatalog& GetMetalKernelCatalog() { return kCatalog; }

const MetalKernelDescriptor* FindMetalKernel(const MetalKernelKind kind) {
  for (const auto& descriptor : kCatalog) {
    if (descriptor.kind == kind) {
      return &descriptor;
    }
  }
  return nullptr;
}

}  // namespace us4
