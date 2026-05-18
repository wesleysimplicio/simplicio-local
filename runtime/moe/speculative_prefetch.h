#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// SpeculativePrefetch tracks how often the router asks for expert N after
// expert M. The runtime uses the observed transition counts to predict which
// experts to prefetch in parallel with the current decode step.
//
// Contract guarantees:
// - the prefetch set never contains experts that the router did not
//   eventually pick within the observation window;
// - the prefetch outcome (hit / miss) is observable through
//   `LastPrefetchHits` and `LastPrefetchAttempts` for telemetry;
// - the predictor is deterministic for a given input sequence.

class SpeculativePrefetch {
 public:
  void Observe(const std::string& previousExpert, const std::string& nextExpert);
  std::vector<std::string> Predict(const std::string& previousExpert,
                                   std::size_t topK) const;
  void RecordOutcome(const std::vector<std::string>& predicted,
                     const std::string& observed);

  std::size_t LastPrefetchAttempts() const { return lastAttempts_; }
  std::size_t LastPrefetchHits() const { return lastHits_; }
  float HitRatio() const;

 private:
  std::unordered_map<std::string, std::unordered_map<std::string, std::size_t>>
      transitions_;
  std::size_t lastAttempts_ = 0;
  std::size_t lastHits_ = 0;
  std::size_t totalAttempts_ = 0;
  std::size_t totalHits_ = 0;
};

}  // namespace us4
