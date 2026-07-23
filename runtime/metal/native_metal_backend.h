#pragma once

#include <cstddef>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace us4 {

struct NativeMetalDevice {
  bool available = false;
  bool supportsUnifiedMemory = false;
  std::size_t maxThreadsPerThreadgroup = 0;
  std::string name;
};

struct NativeMetalMatmulResult {
  bool succeeded = false;
  std::string reason = "metal-native-unavailable";
  std::vector<float> values;
};

class NativeMetalBackend {
public:
  NativeMetalBackend();
  ~NativeMetalBackend();

  NativeMetalBackend(const NativeMetalBackend &) = delete;
  NativeMetalBackend &operator=(const NativeMetalBackend &) = delete;

  bool Compiled() const;
  bool Available() const;
  std::string_view Reason() const;
  const NativeMetalDevice &Device() const;
  NativeMetalMatmulResult
  Matmul(std::span<const float> lhs, std::span<const float> rhs,
         std::size_t rows, std::size_t inner, std::size_t columns);

private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace us4
