#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include "core/hardware_probe.h"
#include "cpu/int8_matmul.h"

namespace us4 {

struct AdvancedKernelObservation {
  CpuInt8Kernel kernel = CpuInt8Kernel::kScalar;
  bool compiled = false;
  bool numerically_correct = false;
  double p50_ms = 0.0;
  double p95_ms = 0.0;
  bool thermal_throttled = false;
  std::size_t minimum_work = 0;
};

struct AdvancedInt8Request {
  HardwareProbeResult hardware;
  std::size_t rows = 0;
  std::size_t inner = 0;
  std::size_t columns = 0;
  std::vector<AdvancedKernelObservation> observations;
  std::string requested_kernel;
  bool force_scalar = false;
};

struct AdvancedInt8Selection {
  CpuInt8Kernel effective_kernel = CpuInt8Kernel::kScalar;
  std::string requested_kernel;
  bool fallback = true;
  bool promoted = false;
  std::string reason;
  double p50_ms = 0.0;
  double p95_ms = 0.0;
};

AdvancedInt8Selection SelectAdvancedInt8Kernel(
    const AdvancedInt8Request& request);

bool IsAdvancedKernelAvailable(CpuInt8Kernel kernel,
                               const HardwareProbeResult& hardware);

}  // namespace us4
