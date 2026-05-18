#include "speculative/eagle3_decoder.h"

#include <algorithm>
#include <sstream>

namespace us4 {

namespace {

std::string ContextKey(const std::vector<std::string> &context) {
  std::ostringstream stream;
  for (std::size_t i = 0; i < context.size(); ++i) {
    if (i > 0) {
      stream << '|';
    }
    stream << context[i];
  }
  return stream.str();
}

} // namespace

Eagle3Decoder::Eagle3Decoder(const std::size_t verifyWindow)
    : verifyWindow_(verifyWindow == 0 ? 1U : verifyWindow) {}

void Eagle3Decoder::RememberNGram(const std::vector<std::string> &sequence) {
  if (sequence.size() < 2U) {
    return;
  }
  std::vector<std::string> context(sequence.begin(), sequence.end() - 1);
  ngrams_[ContextKey(context)].push_back(sequence.back());
}

std::vector<std::string>
Eagle3Decoder::PredictFromContext(const std::vector<std::string> &context,
                                  const std::size_t length) const {
  std::vector<std::string> result;
  const auto it = ngrams_.find(ContextKey(context));
  if (it == ngrams_.end()) {
    return result;
  }
  for (std::size_t index = 0; index < std::min(length, it->second.size());
       ++index) {
    result.push_back(it->second[index]);
  }
  return result;
}

SpeculativeVerifyResult
Eagle3Decoder::Verify(const std::vector<SpeculativeDraftToken> &drafts) const {
  PEagleDecoder verifier(verifyWindow_);
  return verifier.Verify(drafts);
}

} // namespace us4
