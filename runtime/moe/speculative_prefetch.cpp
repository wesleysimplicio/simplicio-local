#include "moe/speculative_prefetch.h"

#include <algorithm>

namespace us4 {

SpeculativePrefetch::SpeculativePrefetch(const std::size_t breadth)
    : breadth_(std::max<std::size_t>(breadth, 1U)) {}

SpeculativePrefetchPlan
SpeculativePrefetch::BuildPlan(const std::string_view family,
                               const RouterDecision &prediction) const {
  SpeculativePrefetchPlan plan;
  plan.family = std::string(family);

  const std::size_t count =
      std::min<std::size_t>(breadth_, prediction.selected.size());
  plan.prefetchedExperts.reserve(count);
  plan.prefetchedKeys.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    const std::size_t expert = prediction.selected[index].expert;
    plan.prefetchedExperts.push_back(expert);
    plan.prefetchedKeys.push_back(plan.family + "-expert-" +
                                  std::to_string(expert));
  }

  return plan;
}

std::vector<std::size_t>
SpeculativePrefetch::ExecutableExperts(const SpeculativePrefetchPlan &,
                                       const RouterDecision &actual) const {
  std::vector<std::size_t> executable;
  executable.reserve(actual.selected.size());
  for (const ExpertScore &expert : actual.selected) {
    executable.push_back(expert.expert);
  }
  return executable;
}

SpeculativePrefetchTelemetry
SpeculativePrefetch::Reconcile(const SpeculativePrefetchPlan &plan,
                               const RouterDecision &actual) const {
  SpeculativePrefetchTelemetry telemetry;
  telemetry.prefetchedCount = plan.prefetchedExperts.size();
  telemetry.executableExperts = ExecutableExperts(plan, actual);

  for (const std::size_t expert : plan.prefetchedExperts) {
    const bool matched = std::find(telemetry.executableExperts.begin(),
                                   telemetry.executableExperts.end(),
                                   expert) != telemetry.executableExperts.end();
    if (matched) {
      ++telemetry.hitCount;
    } else {
      ++telemetry.missCount;
    }
  }

  telemetry.hitRatio = telemetry.prefetchedCount == 0U
                           ? 0.0
                           : static_cast<double>(telemetry.hitCount) /
                                 static_cast<double>(telemetry.prefetchedCount);

  telemetry.wrongExpertLeakPrevented = std::all_of(
      telemetry.executableExperts.begin(), telemetry.executableExperts.end(),
      [&actual](const std::size_t expert) {
        return std::any_of(actual.selected.begin(), actual.selected.end(),
                           [expert](const ExpertScore &actualExpert) {
                             return actualExpert.expert == expert;
                           });
      });
  return telemetry;
}

} // namespace us4
