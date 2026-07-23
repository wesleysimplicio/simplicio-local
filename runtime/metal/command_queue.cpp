#include "metal/command_queue.h"

#include <algorithm>

#include "metal/autorelease_scope.h"
#include "metal/kernel_library.h"

namespace us4 {

std::string_view ToString(const MetalKernelKind kernel) {
  switch (kernel) {
  case MetalKernelKind::kMatmul:
    return "matmul";
  case MetalKernelKind::kSoftmax:
    return "softmax";
  case MetalKernelKind::kRmsNorm:
    return "rmsnorm";
  }
  return "matmul";
}

std::string_view ToString(const MetalInitializationStage stage) {
  switch (stage) {
  case MetalInitializationStage::kUnavailable:
    return "unavailable";
  case MetalInitializationStage::kDeviceReady:
    return "device-ready";
  case MetalInitializationStage::kQueueReady:
    return "queue-ready";
  }
  return "unavailable";
}

MetalCommandQueue::MetalCommandQueue(const HardwareProbeResult &hardware)
    : nativeBackend_(std::make_shared<NativeMetalBackend>()) {
  profile_.requiresAutoreleaseBoundary =
      hardware.platform == "macos" || hardware.platform == "ios";
#if defined(__APPLE__)
  profile_.hostSupportsObjectiveCBoundary = true;
#endif

  profile_.nativeBackendCompiled = nativeBackend_->Compiled();
  profile_.nativeBackendAvailable = nativeBackend_->Available();

  if (!hardware.hasMetal || !hardware.isAppleSilicon) {
    available_ = false;
    reason_ = "metal-unavailable";
    profile_.stage = MetalInitializationStage::kUnavailable;
    return;
  }

  if (!nativeBackend_->Available()) {
    available_ = false;
    reason_ = std::string(nativeBackend_->Reason());
    profile_.stage = MetalInitializationStage::kUnavailable;
    return;
  }

  const NativeMetalDevice &nativeDevice = nativeBackend_->Device();
  device_.available = true;
  device_.supportsUnifiedMemory = nativeDevice.supportsUnifiedMemory;
  device_.maxThreadsPerThreadgroup = nativeDevice.maxThreadsPerThreadgroup;
  device_.deviceName = nativeDevice.name;
  device_.queueLabel = "us4.metal.default";
  profile_.stage = MetalInitializationStage::kQueueReady;
  profile_.queueCreated = true;
  available_ = true;
  reason_ = "metal-native-ready";
}

bool MetalCommandQueue::Available() const { return available_; }

std::string_view MetalCommandQueue::Reason() const { return reason_; }

const MetalDeviceInfo &MetalCommandQueue::Device() const { return device_; }

const MetalQueueProfile &MetalCommandQueue::Profile() const { return profile_; }

bool MetalCommandQueue::Dispatch(
    const MetalKernelKind kernel, const std::size_t threadgroups,
    const std::size_t threadsPerGroup,
    const std::shared_ptr<UnifiedAllocation> &allocation) {
  (void)kernel;
  (void)threadgroups;
  (void)threadsPerGroup;
  (void)allocation;
  reason_ = available_ ? "metal-dispatch-requires-bound-buffers"
                       : std::string(nativeBackend_ != nullptr
                                         ? nativeBackend_->Reason()
                                         : std::string_view("metal-unavailable"));
  return false;
}

bool MetalCommandQueue::Matmul(const std::span<const float> lhs,
                               const std::span<const float> rhs,
                               const std::size_t rows,
                               const std::size_t inner,
                               const std::size_t columns,
                               std::vector<float> &output) {
  if (!available_ || nativeBackend_ == nullptr) {
    reason_ = nativeBackend_ != nullptr ? std::string(nativeBackend_->Reason())
                                        : "metal-unavailable";
    return false;
  }

  NativeMetalMatmulResult result =
      nativeBackend_->Matmul(lhs, rhs, rows, inner, columns);
  reason_ = result.reason;
  if (!result.succeeded) {
    return false;
  }

  const MetalKernelDescriptor *descriptor =
      FindMetalKernel(MetalKernelKind::kMatmul);
  output = std::move(result.values);
  const std::size_t threadsPerGroup =
      std::min<std::size_t>(device_.maxThreadsPerThreadgroup, 256U);
  dispatches_.push_back(MetalDispatchRecord{
      .kernel = MetalKernelKind::kMatmul,
      .entryPoint = descriptor != nullptr ? descriptor->entryPoint
                                          : std::string_view{},
      .relativePath = descriptor != nullptr ? descriptor->relativePath
                                            : std::string_view{},
      .threadgroups =
          (rows * columns + threadsPerGroup - 1U) / threadsPerGroup,
      .threadsPerGroup = threadsPerGroup,
      .usesSharedAllocation = true,
      .autoreleaseBoundaryRequested = true,
      .autoreleasePoolActive = true,
      .autoreleaseBoundaryKind = "objective-c-autorelease",
      .executed = true,
  });
  return true;
}

void MetalCommandQueue::Reset() {
  dispatches_.clear();
  if (profile_.stage == MetalInitializationStage::kQueueReady) {
    reason_ = "metal-queue-ready";
  } else if (profile_.stage == MetalInitializationStage::kDeviceReady) {
    reason_ = "metal-device-ready";
  }
}

std::size_t MetalCommandQueue::DispatchCount() const {
  return dispatches_.size();
}

const std::vector<MetalDispatchRecord> &MetalCommandQueue::Dispatches() const {
  return dispatches_;
}

} // namespace us4
