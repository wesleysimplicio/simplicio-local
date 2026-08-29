#include "cpu/advanced_dispatch.h"

#include <algorithm>
#include <cstdlib>
#include <string_view>

namespace us4 {

namespace {

bool EnvDisabled(const CpuInt8Kernel kernel) {
  const char* raw = std::getenv("US4_DISABLE_ADVANCED_KERNELS");
  if (raw == nullptr || std::string_view(raw) != "1") {
    return false;
  }
  return kernel != CpuInt8Kernel::kScalar;
}

bool BetterThanBaseline(const AdvancedKernelObservation& candidate,
                        const AdvancedKernelObservation& baseline) {
  if (candidate.p50_ms > baseline.p50_ms * 0.98) {
    return false;
  }
  return candidate.p95_ms <= baseline.p95_ms * 1.05;
}

}  // namespace

bool IsAdvancedKernelAvailable(const CpuInt8Kernel kernel,
                               const HardwareProbeResult& hardware) {
  switch (kernel) {
    case CpuInt8Kernel::kScalar:
      return true;
    case CpuInt8Kernel::kX86Avx2:
      return hardware.hasAvx2;
    case CpuInt8Kernel::kX86Vnni:
      return hardware.hasAvx512Vnni;
    case CpuInt8Kernel::kNeonSdot:
      return hardware.hasDotProd;
    case CpuInt8Kernel::kNeonI8mm:
      return hardware.hasI8mm;
  }
  return false;
}

AdvancedInt8Selection SelectAdvancedInt8Kernel(
    const AdvancedInt8Request& request) {
  AdvancedInt8Selection selection;
  selection.requested_kernel = request.requested_kernel;

  const auto scalar = std::find_if(
      request.observations.begin(), request.observations.end(),
      [](const AdvancedKernelObservation& observation) {
        return observation.kernel == CpuInt8Kernel::kScalar;
      });
  if (scalar == request.observations.end() || !scalar->compiled ||
      !scalar->numerically_correct || scalar->p50_ms <= 0.0 ||
      scalar->p95_ms <= 0.0) {
    selection.reason = "measured scalar baseline is required";
    return selection;
  }
  selection.p50_ms = scalar->p50_ms;
  selection.p95_ms = scalar->p95_ms;
  if (request.force_scalar || EnvDisabled(CpuInt8Kernel::kScalar)) {
    selection.reason = "scalar forced by runtime kill switch";
    return selection;
  }

  const std::size_t work = request.rows * request.inner * request.columns;
  const AdvancedKernelObservation* best = nullptr;
  for (const auto& candidate : request.observations) {
    if (candidate.kernel == CpuInt8Kernel::kScalar || !candidate.compiled ||
        !candidate.numerically_correct || candidate.p50_ms <= 0.0 ||
        candidate.p95_ms <= 0.0 || candidate.thermal_throttled ||
        work < candidate.minimum_work || EnvDisabled(candidate.kernel) ||
        !IsAdvancedKernelAvailable(candidate.kernel, request.hardware) ||
        !BetterThanBaseline(candidate, *scalar)) {
      continue;
    }
    if (best == nullptr || candidate.p50_ms < best->p50_ms ||
        (candidate.p50_ms == best->p50_ms && candidate.p95_ms < best->p95_ms)) {
      best = &candidate;
    }
  }
  if (best == nullptr) {
    selection.reason = "no correct measured candidate beat the applicable baseline";
    return selection;
  }
  selection.effective_kernel = best->kernel;
  selection.fallback = false;
  selection.promoted = true;
  selection.p50_ms = best->p50_ms;
  selection.p95_ms = best->p95_ms;
  selection.reason = "candidate passed ISA, correctness, shape and thermal gates";
  return selection;
}

}  // namespace us4
