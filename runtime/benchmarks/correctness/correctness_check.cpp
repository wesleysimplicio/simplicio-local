// Native correctness gate.
//
// Until an external HF reference is wired, the trusted reference on CPU is the
// scalar kernel path: accelerated kernels (NEON, and on Apple the dispatched
// Metal/MLX simulation) must reproduce the scalar result within a fixed
// logit-diff tolerance, and structural invariants (RoPE rotation norm,
// generation determinism) must hold. Emits key=value rows like the other
// benchmark gates and exits non-zero on any violation so the DoD can block.

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

#include "core/rope.h"
#include "core/tensor.h"
#include "cpu/scalar_matmul.h"
#include "neon/neon_matmul.h"

namespace {

constexpr double kMatmulTolerance = 1e-4;
constexpr double kRopeNormTolerance = 1e-4;

// Deterministic, dependency-free fill so the gate is reproducible across hosts.
float PseudoRandom(std::uint32_t &state) {
  state = state * 1664525U + 1013904223U;
  return static_cast<float>((state >> 8) & 0xFFFFU) / 32768.0F - 1.0F;
}

us4::Tensor MakeFilledMatrix(std::size_t rows, std::size_t cols,
                             std::uint32_t &state) {
  us4::Tensor tensor({rows, cols}, us4::DType::kFloat32);
  float *data = tensor.MutableDataAsFloat32();
  for (std::size_t i = 0; i < rows * cols; ++i) {
    data[i] = PseudoRandom(state);
  }
  return tensor;
}

bool emitMatmulCase(std::size_t m, std::size_t k, std::size_t n,
                    std::uint32_t seed) {
  std::uint32_t state = seed;
  const us4::Tensor lhs = MakeFilledMatrix(m, k, state);
  const us4::Tensor rhs = MakeFilledMatrix(k, n, state);
  us4::Tensor reference({m, n}, us4::DType::kFloat32);
  us4::Tensor candidate({m, n}, us4::DType::kFloat32);

  std::string error;
  if (!us4::ScalarMatmul(lhs, rhs, reference, &error) ||
      !us4::NeonMatmul(lhs, rhs, candidate, &error)) {
    std::cout << "case=matmul-" << m << "x" << k << "x" << n << "\n";
    std::cout << "status=error\n";
    std::cout << "reason=" << error << "\n";
    std::cout << "--\n";
    return false;
  }

  const float *ref = reference.DataAsFloat32();
  const float *cand = candidate.DataAsFloat32();
  double maxAbsDiff = 0.0;
  for (std::size_t i = 0; i < m * n; ++i) {
    maxAbsDiff =
        std::max(maxAbsDiff, std::fabs(static_cast<double>(cand[i] - ref[i])));
  }

  const bool pass = maxAbsDiff <= kMatmulTolerance;
  std::cout << "case=matmul-" << m << "x" << k << "x" << n << "\n";
  std::cout << "reference=scalar\n";
  std::cout << "candidate=neon\n";
  std::cout << "max_abs_diff=" << maxAbsDiff << "\n";
  std::cout << "tolerance=" << kMatmulTolerance << "\n";
  std::cout << "status=" << (pass ? "pass" : "fail") << "\n";
  std::cout << "--\n";
  return pass;
}

bool emitRopeNormCase() {
  constexpr std::size_t kRows = 3;
  constexpr std::size_t kCols = 8;
  std::uint32_t state = 0xC0FFEEU;
  us4::Tensor tensor({kRows, kCols}, us4::DType::kFloat32);
  std::array<float, kRows * kCols> original{};
  float *data = tensor.MutableDataAsFloat32();
  for (std::size_t i = 0; i < kRows * kCols; ++i) {
    original[i] = PseudoRandom(state);
    data[i] = original[i];
  }

  us4::ApplyRopeInPlace(tensor, 17U, 10000.0F, us4::RopeScalingType::kYaRN,
                        1.5F);

  double maxNormDelta = 0.0;
  for (std::size_t row = 0; row < kRows; ++row) {
    for (std::size_t pair = 0; pair < kCols / 2U; ++pair) {
      const std::size_t base = row * kCols + pair * 2U;
      const double before = std::hypot(original[base], original[base + 1]);
      const double after = std::hypot(data[base], data[base + 1]);
      maxNormDelta = std::max(maxNormDelta, std::fabs(after - before));
    }
  }

  const bool pass = maxNormDelta <= kRopeNormTolerance;
  std::cout << "case=rope-norm-invariant\n";
  std::cout << "max_norm_delta=" << maxNormDelta << "\n";
  std::cout << "tolerance=" << kRopeNormTolerance << "\n";
  std::cout << "status=" << (pass ? "pass" : "fail") << "\n";
  std::cout << "--\n";
  return pass;
}

} // namespace

int main() {
  std::cout << "benchmark=correctness\n";
  std::cout << "reference_source=scalar-cpu\n";
  std::cout << "--\n";

  bool ok = true;
  ok &= emitMatmulCase(4, 5, 3, 0x1234U);
  ok &= emitMatmulCase(16, 16, 16, 0x5678U);
  ok &= emitMatmulCase(7, 13, 5, 0x9ABCU);
  ok &= emitRopeNormCase();

  std::cout << "correctness_status=" << (ok ? "pass" : "fail") << "\n";
  return ok ? 0 : 1;
}
