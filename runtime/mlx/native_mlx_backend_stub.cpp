#include "mlx/native_mlx_backend.h"

namespace us4 {

class NativeMlxBackend::Impl {
public:
  std::string reason = "mlx-not-built-for-host";
};

NativeMlxBackend::NativeMlxBackend() : impl_(std::make_unique<Impl>()) {}

NativeMlxBackend::~NativeMlxBackend() = default;

bool NativeMlxBackend::Compiled() const { return false; }

bool NativeMlxBackend::Available() const { return false; }

std::string_view NativeMlxBackend::Reason() const { return impl_->reason; }

NativeMlxMatmulResult
NativeMlxBackend::Matmul(std::span<const float> /*lhs*/,
                         std::span<const float> /*rhs*/,
                         const std::size_t /*rows*/,
                         const std::size_t /*inner*/,
                         const std::size_t /*columns*/) {
  return {.succeeded = false, .reason = impl_->reason, .values = {}};
}

} // namespace us4
