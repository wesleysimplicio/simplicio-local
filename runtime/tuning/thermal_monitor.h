#pragma once

#include <string>
#include <string_view>

#include "core/hardware_probe.h"
#include "core/runtime_mode.h"

namespace us4 {

enum class ThermalPressureLevel {
  kUnavailable,
  kNominal,
  kElevated,
  kCritical,
};

struct ThermalSample {
  bool available = false;
  ThermalPressureLevel level = ThermalPressureLevel::kUnavailable;
  std::string source = "none";
  std::string reason = "thermal-unavailable";
};

struct ThermalDecision {
  RuntimeMode requestedMode = RuntimeMode::kNano;
  RuntimeMode effectiveMode = RuntimeMode::kNano;
  ThermalPressureLevel level = ThermalPressureLevel::kUnavailable;
  bool downgraded = false;
  std::string reason = "thermal-unavailable";
};

enum class ThermalState {
  kNominal,
  kFair,
  kSerious,
  kCritical,
};

struct ThermalReading {
  ThermalState state = ThermalState::kNominal;
  float celsius = 0.0F;
  std::string source = "synthetic";
};

struct ThermalDowngradeDecision {
  bool requiresDowngrade = false;
  std::string reason;
};

std::string_view ToString(ThermalPressureLevel level);
ThermalDowngradeDecision DecideThermalDowngrade(const ThermalReading &reading);

class ThermalMonitor {
public:
  ThermalMonitor() = default;
  explicit ThermalMonitor(const HardwareProbeResult &hardware);

  bool Available() const;
  std::string_view Reason() const;
  ThermalSample Sample() const;
  ThermalDecision Decide(RuntimeMode requestedMode);
  const ThermalDecision &LastDecision() const;

private:
  bool available_ = false;
  ThermalSample sample_;
  ThermalDecision lastDecision_;
};

} // namespace us4
