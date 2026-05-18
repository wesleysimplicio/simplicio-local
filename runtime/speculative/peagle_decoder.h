#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace us4 {

// P-EAGLE speculative decoder contract. The target model issues draft tokens
// via a small companion model and verifies a window of speculative tokens
// against the target's actual probabilities. Accept/reject decisions are
// deterministic for a fixed seed and the verified output stays bit-identical
// to the non-speculative path.

struct SpeculativeDraftToken {
  std::string token;
  float draftLogit = 0.0F;
  float targetLogit = 0.0F;
};

struct SpeculativeVerifyResult {
  std::vector<std::string> acceptedTokens;
  std::size_t rejectedAt = std::numeric_limits<std::size_t>::max();
  std::size_t draftAttempts = 0;
  std::size_t accepted = 0;
};

class PEagleDecoder {
 public:
  // The default acceptance window matches the original P-EAGLE paper; the
  // value is exposed for tests and benchmarks to override.
  explicit PEagleDecoder(std::size_t verifyWindow = 4);

  SpeculativeVerifyResult
  Verify(const std::vector<SpeculativeDraftToken>& drafts) const;

 private:
  std::size_t verifyWindow_;
};

}  // namespace us4
