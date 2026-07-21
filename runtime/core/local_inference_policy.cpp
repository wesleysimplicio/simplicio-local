#include "core/local_inference_policy.h"

#include <cstdlib>
#include <string_view>

namespace us4 {

namespace {

bool EqualsEnv(const char *name, const std::string_view expected) {
  const char *value = std::getenv(name);
  return value != nullptr && value == expected;
}

bool HasNonEmptyEnv(const char *name) {
  const char *value = std::getenv(name);
  return value != nullptr && *value != '\0';
}

} // namespace

LocalInferenceAdmission GetLocalInferenceAdmission() {
  if (EqualsEnv("US4_LOCAL_INFERENCE", "enabled") &&
      EqualsEnv("US4_RUNTIME_POLICY", "admitted") &&
      HasNonEmptyEnv("US4_RUNTIME_LEASE")) {
    return {.allowed = true, .reason = "runtime-policy-admitted"};
  }
  return {.allowed = false,
          .reason =
              "local inference is paused by default; require Runtime policy "
              "admission and a non-empty Runtime lease"};
}

} // namespace us4
