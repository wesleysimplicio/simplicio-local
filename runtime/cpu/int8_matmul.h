#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>

namespace us4 {

enum class CpuInt8Kernel {
  kScalar,
  kNeonSdot,
  kNeonI8mm,
  kX86Vnni,
};

struct CpuInt8Capabilities {
  bool neonSdot = false;
  bool neonI8mm = false;
  bool x86Vnni = false;
};

struct CpuInt8Dispatch {
  CpuInt8Kernel kernel = CpuInt8Kernel::kScalar;
  bool accelerated = false;
};

std::string_view ToString(CpuInt8Kernel kernel);
CpuInt8Capabilities DetectCpuInt8Capabilities();
CpuInt8Dispatch SelectCpuInt8Kernel(const CpuInt8Capabilities &capabilities);
CpuInt8Dispatch SelectCpuInt8Kernel();

void ScalarInt8Matmul(const std::int8_t *lhs, const std::int8_t *rhs,
                      std::size_t lhsRows, std::size_t lhsCols,
                      std::size_t rhsCols, float *output);
void CpuInt8Matmul(const std::int8_t *lhs, const std::int8_t *rhs,
                   std::size_t lhsRows, std::size_t lhsCols,
                   std::size_t rhsCols, float *output,
                   CpuInt8Dispatch *dispatch = nullptr);

} // namespace us4
