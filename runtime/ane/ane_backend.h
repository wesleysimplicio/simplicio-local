#pragma once

#include <cstddef>
#include <string>
#include <string_view>

#include "core/hardware_probe.h"

namespace us4 {

// AneBackend contract surface.
//
// The Apple Neural Engine path is opt-in and only viable on M5+ chips. The
// runtime never assumes ANE availability. Instead, the backend exposes a
// readiness probe plus an explicit fallback reason so non-M5 hosts can
// surface the limitation in CLI/bench output.

struct AneReadiness {
  bool available = false;
  std::string chip;          // "M5", "M5 Pro", ...
  std::string fallbackReason; // "chip-too-old", "compile-unavailable", "ready"
};

class AneBackend {
 public:
  AneReadiness Probe(const HardwareProbeResult& hardware) const;

  // CompileForOffload exposes the planned CoreML compile/predict surface. The
  // current implementation reports availability without producing real
  // CoreML artifacts; once the toolchain integration lands this routine
  // owns the compile step.
  bool CompileForOffload(const std::string& modelId, std::string& reason) const;
};

}  // namespace us4
