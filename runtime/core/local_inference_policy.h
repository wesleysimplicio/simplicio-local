#pragma once

#include <string>

namespace us4 {

inline constexpr char kLocalInferencePausedReason[] =
    "LOCAL_INFERENCE_PAUSED";
inline constexpr int kLocalInferencePausedExitCode = 78;

struct LocalInferenceAdmission {
  bool allowed = false;
  std::string reason;
};

// Local model execution is fail-closed. The Runtime must issue both an
// admission decision and a scoped lease before a process may load, spawn,
// proxy, or generate through a local model.
LocalInferenceAdmission GetLocalInferenceAdmission();

} // namespace us4
