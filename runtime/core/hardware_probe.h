#pragma once

#include <string>
#include <vector>

#include "core/runtime_mode.h"

namespace us4 {

struct HardwareProbeResult {
  std::string platform;
  std::string architecture;
  std::string chip;
  unsigned long long unifiedMemoryGiB = 0;
  bool isAppleSilicon = false;
  bool hasMlx = false;
  bool hasMetal = false;
  bool hasCuda = false;
  unsigned long long gpuMemoryGiB = 0;
  unsigned long long cudaMemoryGiB = 0;
  unsigned long long availableMemoryGiB = 0;
  bool hasNeon = false;
  bool hasDotProd = false;
  bool hasI8mm = false;
  bool hasBf16 = false;
  bool hasSve = false;
  bool hasSse41 = false;
  bool hasAvx = false;
  bool hasAvx2 = false;
  bool hasFma = false;
  bool hasAvx512F = false;
  bool hasAvx512Bw = false;
  bool hasAvx512Vl = false;
  bool hasAvx512Vnni = false;
  bool hasAmxInt8 = false;
  bool hasAmxBf16 = false;
  bool osAvxEnabled = false;
  bool osAvx512Enabled = false;
  bool osAmxEnabled = false;
  bool isaOverridden = false;
  std::vector<std::string> isaFeatures;
  std::string isaSource = "unavailable";
  std::string isaReason = "no runtime ISA probe has run";
  bool hasAne = false;
  bool supportsCoreMl = false;
  unsigned int neonVectorBits = 0;
  bool hasPerformanceCores = false;
  bool hasEfficiencyCores = false;
  RuntimeMode recommendedMode = RuntimeMode::kNano;
};

class HardwareProbe {
public:
  static HardwareProbeResult Detect();
};

} // namespace us4
