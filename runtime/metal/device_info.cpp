#include "metal/device_info.h"

namespace us4 {

MetalDeviceInfo ProbeMetalDevice(const HardwareProbeResult& hardware) {
  MetalDeviceInfo device;
  device.available = hardware.hasMetal;
  device.supportsUnifiedMemory = hardware.hasMetal && hardware.isAppleSilicon;
  device.maxThreadsPerThreadgroup = hardware.hasMetal ? 1024U : 0U;
  device.deviceName = hardware.hasMetal ? (hardware.chip.empty() ? "apple-gpu" : hardware.chip + "-gpu") : "unavailable";
  device.queueLabel = hardware.hasMetal ? "us4.metal.default" : "disabled";
  return device;
}

}  // namespace us4
