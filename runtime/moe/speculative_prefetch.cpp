#include "moe/speculative_prefetch.h"

#include <algorithm>

namespace us4 {

void SpeculativePrefetch::Observe(const std::string &previousExpert,
                                  const std::string &nextExpert) {
  ++transitions_[previousExpert][nextExpert];
}

std::vector<std::string>
SpeculativePrefetch::Predict(const std::string &previousExpert,
                             const std::size_t topK) const {
  std::vector<std::string> result;
  const auto it = transitions_.find(previousExpert);
  if (it == transitions_.end() || topK == 0) {
    return result;
  }
  std::vector<std::pair<std::string, std::size_t>> scored(it->second.begin(),
                                                          it->second.end());
  std::sort(scored.begin(), scored.end(),
            [](const std::pair<std::string, std::size_t> &lhs,
               const std::pair<std::string, std::size_t> &rhs) {
              if (lhs.second != rhs.second) {
                return lhs.second > rhs.second;
              }
              return lhs.first < rhs.first;
            });
  for (std::size_t index = 0; index < std::min(topK, scored.size()); ++index) {
    result.push_back(scored[index].first);
  }
  return result;
}

void SpeculativePrefetch::RecordOutcome(
    const std::vector<std::string> &predicted, const std::string &observed) {
  lastAttempts_ = predicted.size();
  lastHits_ = 0;
  for (const auto &candidate : predicted) {
    if (candidate == observed) {
      ++lastHits_;
    }
  }
  totalAttempts_ += lastAttempts_;
  totalHits_ += lastHits_;
}

float SpeculativePrefetch::HitRatio() const {
  if (totalAttempts_ == 0) {
    return 0.0F;
  }
  return static_cast<float>(totalHits_) / static_cast<float>(totalAttempts_);
}

} // namespace us4
