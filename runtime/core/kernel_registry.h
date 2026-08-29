#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace us4 {

// The registry is deliberately independent from the model/runtime planner.
// Planners describe intent; this table owns the physical implementation that
// can be invoked by a hot path.
enum class KernelOperation {
  kInt8Matmul,
  kFloatMatmul,
  kRmsNorm,
  kRope,
  kSoftmax,
};

std::string_view ToString(KernelOperation operation);

using Int8MatmulKernel = void (*)(const std::int8_t*, const std::int8_t*,
                                  std::size_t, std::size_t, std::size_t,
                                  float*);
using FloatMatmulKernel = void (*)(const float*, const float*, std::size_t,
                                   std::size_t, std::size_t, float*);

struct KernelDescriptor {
  std::string name;
  KernelOperation operation = KernelOperation::kInt8Matmul;
  std::string dtype;
  std::vector<std::string> isa_requirements;
  std::string backend = "cpu";
  std::string layout = "row-major";
  bool compiled = false;
  bool portable = false;
  int priority = 0;
};

struct KernelImplementation {
  KernelDescriptor descriptor;
  Int8MatmulKernel int8_matmul = nullptr;
  FloatMatmulKernel float_matmul = nullptr;
};

struct KernelSelection {
  std::string requested_kernel;
  std::string effective_kernel;
  std::string isa;
  bool fallback = false;
  std::string reason;
  const KernelImplementation* implementation = nullptr;
};

class KernelRegistry {
 public:
  bool Register(KernelImplementation implementation);
  const KernelImplementation* Find(std::string_view name) const;
  KernelSelection Select(KernelOperation operation,
                         std::string_view requested_kernel,
                         const std::vector<std::string>& detected_isa,
                         bool force_scalar = false) const;
  std::vector<KernelDescriptor> Catalog() const;
  std::size_t Size() const;

 private:
  std::vector<KernelImplementation> implementations_;
};

}  // namespace us4
