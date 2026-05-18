#include "ane/ane_backend.h"

namespace us4 {

namespace {

bool ChipMeetsAneFloor(const std::string &chip) {
  // Recognise M5 family explicitly so older chips never claim ANE
  // capability. The list is intentionally small until the catalogue
  // grows.
  if (chip.size() >= 2 && chip[0] == 'M') {
    if (chip[1] == '5' || chip[1] == '6' || chip[1] == '7' ||
        chip[1] == '8' || chip[1] == '9') {
      return true;
    }
  }
  return false;
}

} // namespace

AneReadiness AneBackend::Probe(const HardwareProbeResult &hardware) const {
  AneReadiness readiness;
  readiness.chip = hardware.chip;
  if (!hardware.hasAne) {
    readiness.available = false;
    readiness.fallbackReason = "chip-too-old";
    return readiness;
  }
  if (!ChipMeetsAneFloor(hardware.chip)) {
    readiness.available = false;
    readiness.fallbackReason = "chip-too-old";
    return readiness;
  }
  readiness.available = true;
  readiness.fallbackReason = "ready";
  return readiness;
}

bool AneBackend::CompileForOffload(const std::string &modelId,
                                   std::string &reason) const {
  if (modelId.empty()) {
    reason = "missing-model-id";
    return false;
  }
  // Real compile path lands with the CoreML integration. Reporting the
  // deferred state honestly is part of the contract.
  reason = "compile-deferred";
  return false;
}

} // namespace us4
