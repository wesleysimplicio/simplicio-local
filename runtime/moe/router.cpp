#include "moe/router.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>

namespace us4 {

namespace {

std::vector<float> Softmax(const std::vector<float> &logits) {
  if (logits.empty()) {
    return {};
  }

  const float maxLogit = *std::max_element(logits.begin(), logits.end());
  std::vector<float> probabilities(logits.size(), 0.0F);
  float sum = 0.0F;
  for (std::size_t index = 0; index < logits.size(); ++index) {
    probabilities[index] = std::exp(logits[index] - maxLogit);
    sum += probabilities[index];
  }

  if (sum <= std::numeric_limits<float>::epsilon()) {
    const float uniform = 1.0F / static_cast<float>(logits.size());
    std::fill(probabilities.begin(), probabilities.end(), uniform);
    return probabilities;
  }

  for (float &probability : probabilities) {
    probability /= sum;
  }
  return probabilities;
}

float ComputeEntropy(const std::vector<float> &probabilities) {
  float entropy = 0.0F;
  for (const float probability : probabilities) {
    if (probability > std::numeric_limits<float>::epsilon()) {
      entropy -= probability * std::log(probability);
    }
  }
  return entropy;
}

float ComputeLoadBalance(const std::vector<float> &probabilities) {
  if (probabilities.empty()) {
    return 0.0F;
  }

  const float uniform = 1.0F / static_cast<float>(probabilities.size());
  float squaredDistance = 0.0F;
  for (const float probability : probabilities) {
    const float delta = probability - uniform;
    squaredDistance += delta * delta;
  }
  return 1.0F / (1.0F + squaredDistance);
}

} // namespace

RouterDecision Router::RouteTopK(const std::vector<float> &logits,
                                 const std::size_t k) {
  RouterDecision decision;
  decision.totalExperts = logits.size();
  if (logits.empty() || k == 0U) {
    lastDecision_ = decision;
    return decision;
  }

  const std::vector<float> probabilities = Softmax(logits);
  decision.entropy = ComputeEntropy(probabilities);
  decision.loadBalance = ComputeLoadBalance(probabilities);

  decision.selected.reserve(logits.size());
  for (std::size_t index = 0; index < logits.size(); ++index) {
    decision.selected.push_back({
        index,
        probabilities[index],
        logits[index],
    });
  }
  std::sort(decision.selected.begin(), decision.selected.end(),
            [](const ExpertScore &lhs, const ExpertScore &rhs) {
              if (lhs.score == rhs.score) {
                return lhs.expert < rhs.expert;
              }
              return lhs.score > rhs.score;
            });
  if (decision.selected.size() > k) {
    decision.selected.resize(k);
  }
  decision.selectedMass =
      std::accumulate(decision.selected.begin(), decision.selected.end(), 0.0F,
                      [](const float sum, const ExpertScore &score) {
                        return sum + score.score;
                      });

  lastDecision_ = decision;
  return decision;
}

std::vector<ExpertScore> Router::TopK(const std::vector<float> &logits,
                                      const std::size_t k) {
  return RouteTopK(logits, k).selected;
}

const std::optional<RouterDecision> &Router::LastDecision() const {
  return lastDecision_;
}

} // namespace us4
