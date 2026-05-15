#pragma once

#include <cstddef>
#include <string>

#include "core/hardware_probe.h"

namespace us4 {

struct MetalDeviceInfo {
  bool available = false;
  bool supportsUnifiedMemory = false;
  std::size_t maxThreadsPerThreadgroup = 0;
  std::string deviceName;
  std::string queueLabel;
};

MetalDeviceInfo ProbeMetalDevice(const HardwareProbeResult& hardware);

}  // namespace us4
