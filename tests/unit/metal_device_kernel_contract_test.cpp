#include <gtest/gtest.h>

#include "core/hardware_probe.h"
#include "metal/device_info.h"
#include "metal/kernel_library.h"
#include "metal/native_metal_backend.h"

TEST(MetalDeviceContractTest, ProbeCannotInventNativeMetalAvailability) {
  us4::HardwareProbeResult probe;
  probe.hasMetal = true;
  probe.isAppleSilicon = true;
  probe.chip = "Apple M3";

  const us4::MetalDeviceInfo device = us4::ProbeMetalDevice(probe);
  us4::NativeMetalBackend backend;

  EXPECT_EQ(device.available, backend.Available());
  if (backend.Available()) {
    EXPECT_TRUE(device.supportsUnifiedMemory);
    EXPECT_GT(device.maxThreadsPerThreadgroup, 0U);
    EXPECT_EQ(device.queueLabel, "us4.metal.default");
    EXPECT_FALSE(device.deviceName.empty());
  } else {
    EXPECT_EQ(device.maxThreadsPerThreadgroup, 0U);
    EXPECT_EQ(device.queueLabel, "disabled");
    EXPECT_EQ(device.deviceName, "unavailable");
  }
}

TEST(MetalDeviceContractTest, NonAppleMetalHasNoUnifiedMemory) {
  us4::HardwareProbeResult probe;
  probe.hasMetal = true;
  probe.isAppleSilicon = false;

  const us4::MetalDeviceInfo device = us4::ProbeMetalDevice(probe);

  EXPECT_FALSE(device.available);
  EXPECT_FALSE(device.supportsUnifiedMemory);
}

TEST(MetalDeviceContractTest, MissingMetalDisablesDevice) {
  us4::HardwareProbeResult probe;
  probe.hasMetal = false;

  const us4::MetalDeviceInfo device = us4::ProbeMetalDevice(probe);

  EXPECT_FALSE(device.available);
  EXPECT_EQ(device.maxThreadsPerThreadgroup, 0U);
  EXPECT_EQ(device.queueLabel, "disabled");
  EXPECT_EQ(device.deviceName, "unavailable");
}

TEST(MetalKernelLibraryContractTest, CatalogExposesMatmulSoftmaxRmsNorm) {
  const us4::MetalKernelCatalog &catalog = us4::GetMetalKernelCatalog();
  ASSERT_EQ(catalog.size(), 3U);
  for (const us4::MetalKernelDescriptor &descriptor : catalog) {
    EXPECT_FALSE(descriptor.entryPoint.empty());
    EXPECT_FALSE(descriptor.relativePath.empty());
    EXPECT_FALSE(descriptor.source.empty());
  }
}

TEST(MetalKernelLibraryContractTest, FindResolvesEveryKernelKind) {
  for (const us4::MetalKernelKind kind :
       {us4::MetalKernelKind::kMatmul, us4::MetalKernelKind::kSoftmax,
        us4::MetalKernelKind::kRmsNorm}) {
    const us4::MetalKernelDescriptor *descriptor = us4::FindMetalKernel(kind);
    ASSERT_NE(descriptor, nullptr);
    EXPECT_EQ(descriptor->kind, kind);
  }
  EXPECT_EQ(us4::FindMetalKernel(us4::MetalKernelKind::kMatmul)->entryPoint,
            "us4_matmul_fp32");
}
