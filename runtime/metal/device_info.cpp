#include "metal/device_info.h"

#include "metal/native_metal_backend.h"

namespace us4 {

MetalDeviceInfo ProbeMetalDevice(const HardwareProbeResult& hardware) {
  MetalDeviceInfo device;
  if (!hardware.hasMetal || !hardware.isAppleSilicon) {
    device.deviceName = "unavailable";
    device.queueLabel = "disabled";
    return device;
  }

  NativeMetalBackend backend;
  if (!backend.Available()) {
    device.deviceName = "unavailable";
    device.queueLabel = "disabled";
    return device;
  }

  device.available = true;
  device.supportsUnifiedMemory = backend.Device().supportsUnifiedMemory;
  device.maxThreadsPerThreadgroup = backend.Device().maxThreadsPerThreadgroup;
  device.deviceName = backend.Device().name;
  device.queueLabel = "us4.metal.default";
  return device;
}

}  // namespace us4
