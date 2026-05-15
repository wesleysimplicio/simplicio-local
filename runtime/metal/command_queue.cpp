#include "metal/command_queue.h"

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

MetalCommandQueue::MetalCommandQueue(const HardwareProbeResult& hardware)
    : available_(hardware.hasMetal),
      device_(ProbeMetalDevice(hardware)),
      reason_(hardware.hasMetal ? "metal-queue-ready" : "metal-unavailable") {}

bool MetalCommandQueue::Available() const { return available_; }

std::string_view MetalCommandQueue::Reason() const { return reason_; }

const MetalDeviceInfo& MetalCommandQueue::Device() const { return device_; }

bool MetalCommandQueue::Dispatch(const MetalKernelKind kernel,
                                 const std::size_t threadgroups,
                                 const std::size_t threadsPerGroup,
                                 const std::shared_ptr<UnifiedAllocation>& allocation) {
  if (!available_ || threadgroups == 0 || threadsPerGroup == 0) {
    return false;
  }

  const MetalKernelDescriptor* descriptor = FindMetalKernel(kernel);
  if (descriptor == nullptr) {
    reason_ = "metal-kernel-missing";
    return false;
  }

  ScopedAutoreleasePool pool;
  (void)pool;

  dispatches_.push_back(MetalDispatchRecord{
      .kernel = kernel,
      .entryPoint = descriptor->entryPoint,
      .relativePath = descriptor->relativePath,
      .threadgroups = threadgroups,
      .threadsPerGroup = threadsPerGroup,
      .usesSharedAllocation = allocation != nullptr && allocation->gpuVisible,
  });
  reason_ = "metal-dispatch-recorded";
  return true;
}

void MetalCommandQueue::Reset() {
  dispatches_.clear();
  if (available_) {
    reason_ = "metal-queue-ready";
  }
}

std::size_t MetalCommandQueue::DispatchCount() const { return dispatches_.size(); }

const std::vector<MetalDispatchRecord>& MetalCommandQueue::Dispatches() const { return dispatches_; }

}  // namespace us4
