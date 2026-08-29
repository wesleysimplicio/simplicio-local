#include "core/hardware_probe.h"

#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <sstream>
#include <string_view>
#include <vector>

#if defined(__APPLE__)
#include <sys/sysctl.h>
#endif

#if defined(__linux__)
#include <sys/auxv.h>
#include <sys/syscall.h>
#include <unistd.h>
#if __has_include(<asm/prctl.h>)
#include <asm/prctl.h>
#endif
#if __has_include(<asm/hwcap.h>)
#include <asm/hwcap.h>
#endif
#endif

#if defined(__x86_64__) || defined(_M_X64)
#if defined(_MSC_VER)
#include <intrin.h>
#elif defined(__GNUC__) || defined(__clang__)
#include <cpuid.h>
#endif
#endif

namespace us4 {

namespace {

bool ReadBoolEnv(const char *name, const bool fallback) {
  const char *value = std::getenv(name);
  if (value == nullptr) {
    return fallback;
  }
  return std::string_view(value) == "1" || std::string_view(value) == "true" ||
         std::string_view(value) == "TRUE";
}

unsigned int ReadUnsignedEnv(const char *name, const unsigned int fallback) {
  const char *value = std::getenv(name);
  if (value == nullptr) {
    return fallback;
  }
  return static_cast<unsigned int>(std::strtoul(value, nullptr, 10));
}

unsigned long long DetectMemoryGiB() {
#if defined(__APPLE__)
  std::uint64_t memory_bytes = 0;
  size_t size = sizeof(memory_bytes);
  if (sysctlbyname("hw.memsize", &memory_bytes, &size, nullptr, 0) == 0 &&
      memory_bytes > 0) {
    return memory_bytes / (1024ULL * 1024ULL * 1024ULL);
  }
#endif
  const char *from_env = std::getenv("US4_MEMORY_GIB");
  if (from_env != nullptr) {
    return std::strtoull(from_env, nullptr, 10);
  }
  return 16ULL;
}

unsigned long long ReadMemoryEnv(const char *name,
                                 const unsigned long long fallback) {
  const char *value = std::getenv(name);
  if (value == nullptr) {
    return fallback;
  }
  return std::strtoull(value, nullptr, 10);
}

void AddFeature(std::vector<std::string> &features, const bool enabled,
                const char *name) {
  if (enabled) {
    features.emplace_back(name);
  }
}

bool ReadFeatureEnv(const char *name, const bool fallback = false) {
  return ReadBoolEnv(name, fallback);
}

#if defined(__x86_64__) || defined(_M_X64)
struct CpuidLeaf {
  std::uint32_t eax = 0;
  std::uint32_t ebx = 0;
  std::uint32_t ecx = 0;
  std::uint32_t edx = 0;
};

bool ReadCpuid(const std::uint32_t leaf, const std::uint32_t subleaf,
               CpuidLeaf &result) {
#if defined(_MSC_VER)
  int values[4] = {};
  __cpuidex(values, static_cast<int>(leaf), static_cast<int>(subleaf));
  result = {static_cast<std::uint32_t>(values[0]),
            static_cast<std::uint32_t>(values[1]),
            static_cast<std::uint32_t>(values[2]),
            static_cast<std::uint32_t>(values[3])};
  return true;
#elif defined(__GNUC__) || defined(__clang__)
  return __get_cpuid_count(leaf, subleaf, &result.eax, &result.ebx,
                           &result.ecx, &result.edx) != 0;
#else
  (void)leaf;
  (void)subleaf;
  (void)result;
  return false;
#endif
}

std::uint64_t ReadXcr0() {
#if defined(_MSC_VER)
  return static_cast<std::uint64_t>(_xgetbv(0));
#elif defined(__GNUC__) || defined(__clang__)
  std::uint32_t eax = 0;
  std::uint32_t edx = 0;
  // Keep the translation unit baseline-safe: this instruction is reached
  // only after CPUID reports OSXSAVE. The raw encoding avoids requiring
  // -mxsave on the whole executable.
  __asm__ volatile("xgetbv" : "=a"(eax), "=d"(edx) : "c"(0));
  return (static_cast<std::uint64_t>(edx) << 32U) | eax;
#else
  return 0;
#endif
}

bool LinuxAmxPermission() {
#if defined(__linux__) && defined(ARCH_GET_XCOMP_PERM)
  unsigned long long permission = 0;
  constexpr unsigned long long kAmxTilePermission = 1ULL << 18U;
  if (syscall(SYS_arch_prctl, ARCH_GET_XCOMP_PERM, &permission) == 0) {
    return (permission & kAmxTilePermission) != 0;
  }
#endif
  return false;
}

void DetectX86Isa(HardwareProbeResult &result) {
  CpuidLeaf basic;
  CpuidLeaf extended;
  if (!ReadCpuid(0, 0, basic)) {
    result.isaSource = "unavailable";
    result.isaReason = "CPUID is unavailable on this compiler/architecture";
    return;
  }

  CpuidLeaf leaf1;
  const bool hasLeaf1 = ReadCpuid(1, 0, leaf1);
  const bool osxsave = hasLeaf1 && ((leaf1.ecx & (1U << 27U)) != 0);
  const std::uint64_t xcr0 = osxsave ? ReadXcr0() : 0;
  result.osAvxEnabled = osxsave && ((xcr0 & 0x6U) == 0x6U);
  result.osAvx512Enabled = result.osAvxEnabled &&
                           ((xcr0 & 0xE6U) == 0xE6U);

  const bool cpuSse41 = hasLeaf1 && ((leaf1.ecx & (1U << 19U)) != 0);
  const bool cpuAvx = hasLeaf1 && ((leaf1.ecx & (1U << 28U)) != 0);
  const bool cpuFma = hasLeaf1 && ((leaf1.ecx & (1U << 12U)) != 0);
  CpuidLeaf leaf7;
  const bool hasLeaf7 = basic.eax >= 7U && ReadCpuid(7, 0, leaf7);
  const bool cpuAvx2 = hasLeaf7 && ((leaf7.ebx & (1U << 5U)) != 0);
  const bool cpuAvx512F = hasLeaf7 && ((leaf7.ebx & (1U << 16U)) != 0);
  const bool cpuAvx512Bw = hasLeaf7 && ((leaf7.ebx & (1U << 30U)) != 0);
  const bool cpuAvx512Vl = hasLeaf7 && ((leaf7.ebx & (1U << 31U)) != 0);
  const bool cpuAvx512Vnni = hasLeaf7 && ((leaf7.ecx & (1U << 11U)) != 0);
  const bool cpuAmxBf16 = hasLeaf7 && ((leaf7.edx & (1U << 22U)) != 0);
  const bool cpuAmxTile = hasLeaf7 && ((leaf7.edx & (1U << 24U)) != 0);
  const bool cpuAmxInt8 = hasLeaf7 && ((leaf7.edx & (1U << 25U)) != 0);

  result.hasSse41 = cpuSse41;
  result.hasAvx = cpuAvx && result.osAvxEnabled;
  result.hasFma = cpuFma && result.osAvxEnabled;
  result.hasAvx2 = cpuAvx2 && result.osAvxEnabled;
  result.hasAvx512F = cpuAvx512F && result.osAvx512Enabled;
  result.hasAvx512Bw = cpuAvx512Bw && result.osAvx512Enabled;
  result.hasAvx512Vl = cpuAvx512Vl && result.osAvx512Enabled;
  result.hasAvx512Vnni = cpuAvx512Vnni && result.osAvx512Enabled;
#if defined(__linux__)
  const bool amxPermission = LinuxAmxPermission();
#else
  const bool amxPermission = true;
#endif
  result.osAmxEnabled = cpuAmxTile && ((xcr0 & 0x60000U) == 0x60000U) &&
                        amxPermission;
  result.hasAmxInt8 = cpuAmxInt8 && result.osAmxEnabled;
  result.hasAmxBf16 = cpuAmxBf16 && result.osAmxEnabled;
  result.isaSource = "runtime CPUID + XCR0 + OS state";
  result.isaReason = "x86 feature bits were gated by operating-system state";
}
#endif

void DetectArmIsa(HardwareProbeResult &result) {
  if (result.architecture != "arm64") {
    return;
  }
  result.hasNeon = true;
#if defined(__linux__) && defined(AT_HWCAP)
  const unsigned long hwcap = getauxval(AT_HWCAP);
  (void)hwcap;
#ifdef HWCAP_ASIMD
  result.hasNeon = (hwcap & HWCAP_ASIMD) != 0;
#endif
#ifdef HWCAP_ASIMDDP
  result.hasDotProd = (hwcap & HWCAP_ASIMDDP) != 0;
#endif
#ifdef HWCAP_I8MM
  result.hasI8mm = (hwcap & HWCAP_I8MM) != 0;
#endif
#ifdef HWCAP_SVE
  result.hasSve = (hwcap & HWCAP_SVE) != 0;
#endif
#ifdef HWCAP2_SVE2
  const unsigned long hwcap2 = getauxval(AT_HWCAP2);
  result.hasSve = result.hasSve || ((hwcap2 & HWCAP2_SVE2) != 0);
#endif
#endif
#if defined(__APPLE__)
  int value = 0;
  size_t size = sizeof(value);
  auto sysctlFeature = [&value, &size](const char *name) {
    value = 0;
    size = sizeof(value);
    return sysctlbyname(name, &value, &size, nullptr, 0) == 0 && value != 0;
  };
  result.hasDotProd = sysctlFeature("hw.optional.arm.FEAT_DotProd");
  result.hasI8mm = sysctlFeature("hw.optional.arm.FEAT_I8MM");
  result.hasBf16 = sysctlFeature("hw.optional.arm.FEAT_BF16");
  result.hasSve = sysctlFeature("hw.optional.arm.FEAT_SVE");
#endif
  result.hasDotProd = ReadFeatureEnv("US4_HAS_DOTPROD", result.hasDotProd);
  result.hasI8mm = ReadFeatureEnv("US4_HAS_I8MM", result.hasI8mm);
  result.hasBf16 = ReadFeatureEnv("US4_HAS_BF16", result.hasBf16);
  result.hasSve = ReadFeatureEnv("US4_HAS_SVE", result.hasSve);
  result.isaSource = "runtime HWCAP/sysctl + compile baseline";
  result.isaReason = "ARM capabilities were read from platform feature APIs";
}

void ApplyIsaOverride(HardwareProbeResult &result) {
  const char *raw = std::getenv("US4_ISA_OVERRIDE");
  if (raw == nullptr || *raw == '\0') {
    return;
  }
  result.isaOverridden = true;
  result.isaFeatures.clear();
  std::string token;
  std::istringstream stream(raw);
  while (std::getline(stream, token, ',')) {
    token.erase(std::remove_if(token.begin(), token.end(),
                               [](const unsigned char value) {
                                 return value == ' ' || value == '\t';
                               }),
                token.end());
    if (!token.empty()) {
      result.isaFeatures.push_back(token);
    }
  }
  result.isaSource = "environment override";
  result.isaReason = "US4_ISA_OVERRIDE is diagnostic/test input; not hardware proof";
}

void BuildIsaFeatureList(HardwareProbeResult &result) {
  result.isaFeatures.clear();
  AddFeature(result.isaFeatures, result.hasSse41, "sse4.1");
  AddFeature(result.isaFeatures, result.hasAvx, "avx");
  AddFeature(result.isaFeatures, result.hasAvx2, "avx2");
  AddFeature(result.isaFeatures, result.hasFma, "fma");
  AddFeature(result.isaFeatures, result.hasAvx512F, "avx512f");
  AddFeature(result.isaFeatures, result.hasAvx512Bw, "avx512bw");
  AddFeature(result.isaFeatures, result.hasAvx512Vl, "avx512vl");
  AddFeature(result.isaFeatures, result.hasAvx512Vnni, "avx512vnni");
  AddFeature(result.isaFeatures, result.hasAmxInt8, "amx-int8");
  AddFeature(result.isaFeatures, result.hasAmxBf16, "amx-bf16");
  AddFeature(result.isaFeatures, result.hasNeon, "neon");
  AddFeature(result.isaFeatures, result.hasDotProd, "dotprod");
  AddFeature(result.isaFeatures, result.hasI8mm, "i8mm");
  AddFeature(result.isaFeatures, result.hasBf16, "bf16");
  AddFeature(result.isaFeatures, result.hasSve, "sve");
  std::sort(result.isaFeatures.begin(), result.isaFeatures.end());
}

std::string DetectPlatform() {
#if defined(_WIN32)
  return "windows";
#elif defined(__APPLE__)
  return "apple";
#elif defined(__linux__)
  return "linux";
#else
  return "unknown";
#endif
}

std::string DetectArchitecture() {
#if defined(__aarch64__) || defined(_M_ARM64)
  return "arm64";
#elif defined(__x86_64__) || defined(_M_X64)
  return "x64";
#else
  return "unknown";
#endif
}

std::string DetectChip(bool is_apple_silicon) {
#if defined(__APPLE__) && defined(__aarch64__)
  char buffer[256] = {};
  size_t size = sizeof(buffer);
  if (sysctlbyname("machdep.cpu.brand_string", &buffer, &size, nullptr, 0) ==
          0 &&
      buffer[0] != '\0') {
    return std::string(buffer);
  }
  return "apple-silicon";
#else
  if (is_apple_silicon) {
    return "apple-silicon";
  }
  return "generic-host";
#endif
}

bool DetectAneSupport(const bool isAppleSilicon, const std::string &chip) {
  if (ReadBoolEnv("US4_HAS_ANE", false)) {
    return true;
  }
  if (!isAppleSilicon) {
    return false;
  }
  return chip.find("M5") != std::string::npos ||
         chip.find("apple-m5") != std::string::npos;
}

} // namespace

HardwareProbeResult HardwareProbe::Detect() {
  HardwareProbeResult result;
  result.platform = DetectPlatform();
  result.architecture = DetectArchitecture();
  result.isAppleSilicon =
      (result.platform == "apple" && result.architecture == "arm64");
  result.unifiedMemoryGiB = DetectMemoryGiB();
  result.availableMemoryGiB = ReadMemoryEnv("US4_AVAILABLE_MEMORY_GIB",
                                           result.unifiedMemoryGiB);
  result.hasCuda = ReadBoolEnv("US4_HAS_CUDA", false);
  result.cudaMemoryGiB = ReadMemoryEnv("US4_CUDA_MEMORY_GIB", 0);
  result.gpuMemoryGiB =
      ReadMemoryEnv("US4_GPU_MEMORY_GIB", result.cudaMemoryGiB);
  result.hasMlx = result.isAppleSilicon;
  result.hasMetal = result.isAppleSilicon;
  DetectArmIsa(result);
#if defined(__x86_64__) || defined(_M_X64)
  DetectX86Isa(result);
#endif
  result.neonVectorBits =
      ReadUnsignedEnv("US4_NEON_VECTOR_BITS", result.hasNeon ? 128U : 0U);
  result.hasPerformanceCores =
      ReadBoolEnv("US4_HAS_PERFORMANCE_CORES", result.isAppleSilicon);
  result.hasEfficiencyCores =
      ReadBoolEnv("US4_HAS_EFFICIENCY_CORES", result.isAppleSilicon);
  result.chip = DetectChip(result.isAppleSilicon);
  result.hasAne = DetectAneSupport(result.isAppleSilicon, result.chip);
  result.supportsCoreMl =
      result.hasAne || ReadBoolEnv("US4_SUPPORTS_COREML", false);
  result.recommendedMode =
      SelectRuntimeModeFromMemoryGiB(result.unifiedMemoryGiB);
  BuildIsaFeatureList(result);
  ApplyIsaOverride(result);
  return result;
}

} // namespace us4
