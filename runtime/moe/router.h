#pragma once

#include <cstddef>
#include <optional>
#include <vector>

namespace us4 {

struct ExpertScore {
  std::size_t expert = 0;
  float score = 0.0F;
  float logit = 0.0F;
};

struct RouterDecision {
  std::vector<ExpertScore> selected;
  float entropy = 0.0F;
  float loadBalance = 0.0F;
  float selectedMass = 0.0F;
  std::size_t totalExperts = 0;
};

class Router {
public:
  RouterDecision RouteTopK(const std::vector<float> &logits, std::size_t k);
  std::vector<ExpertScore> TopK(const std::vector<float> &logits,
                                std::size_t k);
  const std::optional<RouterDecision> &LastDecision() const;

private:
  std::optional<RouterDecision> lastDecision_;
};

} // namespace us4
