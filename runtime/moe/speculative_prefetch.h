#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

#include "moe/router.h"

namespace us4 {

struct SpeculativePrefetchPlan {
  std::string family;
  std::vector<std::size_t> prefetchedExperts;
  std::vector<std::string> prefetchedKeys;
};

struct SpeculativePrefetchTelemetry {
  std::size_t prefetchedCount = 0;
  std::size_t hitCount = 0;
  std::size_t missCount = 0;
  double hitRatio = 0.0;
  bool wrongExpertLeakPrevented = true;
  std::vector<std::size_t> executableExperts;
};

class SpeculativePrefetch {
public:
  explicit SpeculativePrefetch(std::size_t breadth = 3U);

  SpeculativePrefetchPlan BuildPlan(std::string_view family,
                                    const RouterDecision &prediction) const;
  std::vector<std::size_t>
  ExecutableExperts(const SpeculativePrefetchPlan &plan,
                    const RouterDecision &actual) const;
  SpeculativePrefetchTelemetry Reconcile(const SpeculativePrefetchPlan &plan,
                                         const RouterDecision &actual) const;

private:
  std::size_t breadth_;
};

} // namespace us4
