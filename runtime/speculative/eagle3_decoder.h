#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>
#include <vector>

#include "speculative/peagle_decoder.h"

namespace us4 {

// EAGLE-3 extends P-EAGLE with an n-gram tree that captures multi-token
// patterns. The decoder reuses the verify-window semantics but adds an
// n-gram lookup so the verifier can short-circuit obvious patterns.

class Eagle3Decoder {
 public:
  explicit Eagle3Decoder(std::size_t verifyWindow = 4);

  void RememberNGram(const std::vector<std::string>& sequence);
  std::vector<std::string> PredictFromContext(
      const std::vector<std::string>& context, std::size_t length) const;
  SpeculativeVerifyResult Verify(
      const std::vector<SpeculativeDraftToken>& drafts) const;

 private:
  std::size_t verifyWindow_;
  std::unordered_map<std::string, std::vector<std::string>> ngrams_;
};

}  // namespace us4
