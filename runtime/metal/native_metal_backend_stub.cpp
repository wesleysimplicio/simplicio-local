#include "metal/native_metal_backend.h"

namespace us4 {

class NativeMetalBackend::Impl {
public:
  NativeMetalDevice device;
  std::string reason = "metal-not-built-for-host";
};

NativeMetalBackend::NativeMetalBackend() : impl_(std::make_unique<Impl>()) {}

NativeMetalBackend::~NativeMetalBackend() = default;

bool NativeMetalBackend::Compiled() const { return false; }

bool NativeMetalBackend::Available() const { return false; }

std::string_view NativeMetalBackend::Reason() const { return impl_->reason; }

const NativeMetalDevice &NativeMetalBackend::Device() const {
  return impl_->device;
}

NativeMetalMatmulResult
NativeMetalBackend::Matmul(std::span<const float> /*lhs*/,
                           std::span<const float> /*rhs*/,
                           const std::size_t /*rows*/,
                           const std::size_t /*inner*/,
                           const std::size_t /*columns*/) {
  return {.succeeded = false, .reason = impl_->reason, .values = {}};
}

} // namespace us4
