#include "metal/native_metal_backend.h"

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>

#include "metal/kernel_library.h"

namespace us4 {

class NativeMetalBackend::Impl {
public:
  Impl() {
    @autoreleasepool {
      device = MTLCreateSystemDefaultDevice();
      if (device == nil) {
        reason = "metal-device-unavailable";
        return;
      }

      queue = [device newCommandQueue];
      if (queue == nil) {
        reason = "metal-command-queue-creation-failed";
        return;
      }

      const MetalKernelDescriptor *descriptor =
          FindMetalKernel(MetalKernelKind::kMatmul);
      if (descriptor == nullptr) {
        reason = "metal-matmul-kernel-missing";
        return;
      }

      NSString *source =
          [[NSString alloc] initWithBytes:descriptor->source.data()
                                  length:descriptor->source.size()
                                encoding:NSUTF8StringEncoding];
      NSError *error = nil;
      id<MTLLibrary> library = [device newLibraryWithSource:source
                                                    options:nil
                                                      error:&error];
      if (library == nil) {
        reason = "metal-library-compilation-failed";
        return;
      }

      NSString *entryPoint =
          [[NSString alloc] initWithBytes:descriptor->entryPoint.data()
                                  length:descriptor->entryPoint.size()
                                encoding:NSUTF8StringEncoding];
      id<MTLFunction> function = [library newFunctionWithName:entryPoint];
      if (function == nil) {
        reason = "metal-matmul-function-missing";
        return;
      }

      pipeline = [device newComputePipelineStateWithFunction:function
                                                       error:&error];
      if (pipeline == nil) {
        reason = "metal-pipeline-creation-failed";
        return;
      }

      profile.available = true;
      profile.supportsUnifiedMemory = device.hasUnifiedMemory;
      profile.maxThreadsPerThreadgroup = pipeline.maxTotalThreadsPerThreadgroup;
      profile.name = device.name.UTF8String;
      reason = "metal-native-ready";
    }
  }

  id<MTLDevice> device = nil;
  id<MTLCommandQueue> queue = nil;
  id<MTLComputePipelineState> pipeline = nil;
  NativeMetalDevice profile;
  std::string reason = "metal-native-unavailable";
};

NativeMetalBackend::NativeMetalBackend() : impl_(std::make_unique<Impl>()) {}

NativeMetalBackend::~NativeMetalBackend() = default;

bool NativeMetalBackend::Compiled() const { return true; }

bool NativeMetalBackend::Available() const { return impl_->profile.available; }

std::string_view NativeMetalBackend::Reason() const { return impl_->reason; }

const NativeMetalDevice &NativeMetalBackend::Device() const {
  return impl_->profile;
}

NativeMetalMatmulResult
NativeMetalBackend::Matmul(const std::span<const float> lhs,
                           const std::span<const float> rhs,
                           const std::size_t rows,
                           const std::size_t inner,
                           const std::size_t columns) {
  if (!Available()) {
    return {.succeeded = false, .reason = impl_->reason, .values = {}};
  }
  if (rows == 0 || inner == 0 || columns == 0 ||
      rows > std::numeric_limits<std::size_t>::max() / inner ||
      inner > std::numeric_limits<std::size_t>::max() / columns ||
      rows > std::numeric_limits<std::size_t>::max() / columns ||
      lhs.size() != rows * inner || rhs.size() != inner * columns ||
      inner > std::numeric_limits<std::uint32_t>::max() ||
      columns > std::numeric_limits<std::uint32_t>::max()) {
    return {.succeeded = false,
            .reason = "metal-matmul-invalid-shape",
            .values = {}};
  }

  @autoreleasepool {
    const std::size_t outputCount = rows * columns;
    id<MTLBuffer> lhsBuffer =
        [impl_->device newBufferWithBytes:lhs.data()
                                  length:lhs.size_bytes()
                                 options:MTLResourceStorageModeShared];
    id<MTLBuffer> rhsBuffer =
        [impl_->device newBufferWithBytes:rhs.data()
                                  length:rhs.size_bytes()
                                 options:MTLResourceStorageModeShared];
    id<MTLBuffer> outputBuffer =
        [impl_->device newBufferWithLength:outputCount * sizeof(float)
                                   options:MTLResourceStorageModeShared];
    if (lhsBuffer == nil || rhsBuffer == nil || outputBuffer == nil) {
      return {.succeeded = false,
              .reason = "metal-buffer-allocation-failed",
              .values = {}};
    }

    id<MTLCommandBuffer> commandBuffer = [impl_->queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder =
        [commandBuffer computeCommandEncoder];
    if (commandBuffer == nil || encoder == nil) {
      return {.succeeded = false,
              .reason = "metal-command-encoding-failed",
              .values = {}};
    }

    const std::uint32_t innerValue = static_cast<std::uint32_t>(inner);
    const std::uint32_t columnsValue = static_cast<std::uint32_t>(columns);
    [encoder setComputePipelineState:impl_->pipeline];
    [encoder setBuffer:lhsBuffer offset:0 atIndex:0];
    [encoder setBuffer:rhsBuffer offset:0 atIndex:1];
    [encoder setBuffer:outputBuffer offset:0 atIndex:2];
    [encoder setBytes:&innerValue length:sizeof(innerValue) atIndex:3];
    [encoder setBytes:&columnsValue length:sizeof(columnsValue) atIndex:4];

    const NSUInteger width = std::min<NSUInteger>(
        impl_->pipeline.maxTotalThreadsPerThreadgroup, 256U);
    [encoder dispatchThreads:MTLSizeMake(outputCount, 1U, 1U)
        threadsPerThreadgroup:MTLSizeMake(width, 1U, 1U)];
    [encoder endEncoding];
    [commandBuffer commit];
    [commandBuffer waitUntilCompleted];

    if (commandBuffer.status != MTLCommandBufferStatusCompleted) {
      return {.succeeded = false,
              .reason = "metal-command-buffer-failed",
              .values = {}};
    }

    std::vector<float> output(outputCount);
    std::memcpy(output.data(), outputBuffer.contents,
                output.size() * sizeof(float));
    return {.succeeded = true,
            .reason = "metal-matmul-executed",
            .values = std::move(output)};
  }
}

} // namespace us4
