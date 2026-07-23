#include "mlx/native_mlx_backend.h"

#include <algorithm>
#include <limits>

#include <mlx/mlx.h>

namespace us4 {

namespace mx = mlx::core;

class NativeMlxBackend::Impl {
public:
  bool available = true;
  std::string reason = "mlx-native-ready";
};

NativeMlxBackend::NativeMlxBackend() : impl_(std::make_unique<Impl>()) {}

NativeMlxBackend::~NativeMlxBackend() = default;

bool NativeMlxBackend::Compiled() const { return true; }

bool NativeMlxBackend::Available() const { return impl_->available; }

std::string_view NativeMlxBackend::Reason() const { return impl_->reason; }

NativeMlxMatmulResult
NativeMlxBackend::Matmul(const std::span<const float> lhs,
                         const std::span<const float> rhs,
                         const std::size_t rows,
                         const std::size_t inner,
                         const std::size_t columns) {
  if (rows == 0 || inner == 0 || columns == 0 ||
      rows > std::numeric_limits<std::size_t>::max() / inner ||
      inner > std::numeric_limits<std::size_t>::max() / columns ||
      rows > std::numeric_limits<std::size_t>::max() / columns ||
      lhs.size() != rows * inner || rhs.size() != inner * columns ||
      rows > std::numeric_limits<int>::max() ||
      inner > std::numeric_limits<int>::max() ||
      columns > std::numeric_limits<int>::max()) {
    return {.succeeded = false,
            .reason = "mlx-matmul-invalid-shape",
            .values = {}};
  }

  try {
    const std::vector<float> lhsValues(lhs.begin(), lhs.end());
    const std::vector<float> rhsValues(rhs.begin(), rhs.end());
    const mx::array lhsArray(
        lhsValues.begin(),
        {static_cast<int>(rows), static_cast<int>(inner)});
    const mx::array rhsArray(
        rhsValues.begin(),
        {static_cast<int>(inner), static_cast<int>(columns)});
    const mx::array result = mx::matmul(lhsArray, rhsArray);
    mx::eval(result);

    std::vector<float> output(rows * columns);
    std::copy_n(result.data<float>(), output.size(), output.begin());
    return {.succeeded = true,
            .reason = "mlx-matmul-evaluated",
            .values = std::move(output)};
  } catch (...) {
    return {.succeeded = false,
            .reason = "mlx-evaluation-failed",
            .values = {}};
  }
}

} // namespace us4
