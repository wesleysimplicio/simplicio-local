#pragma once

#include <cstddef>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace us4 {

struct NativeMlxMatmulResult {
  bool succeeded = false;
  std::string reason = "mlx-native-unavailable";
  std::vector<float> values;
};

class NativeMlxBackend {
public:
  NativeMlxBackend();
  ~NativeMlxBackend();

  NativeMlxBackend(const NativeMlxBackend &) = delete;
  NativeMlxBackend &operator=(const NativeMlxBackend &) = delete;

  bool Compiled() const;
  bool Available() const;
  std::string_view Reason() const;
  NativeMlxMatmulResult
  Matmul(std::span<const float> lhs, std::span<const float> rhs,
         std::size_t rows, std::size_t inner, std::size_t columns);

private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace us4
