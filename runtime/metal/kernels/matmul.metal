#include <metal_stdlib>
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
