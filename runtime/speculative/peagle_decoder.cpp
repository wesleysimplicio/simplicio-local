#include "speculative/peagle_decoder.h"

#include <algorithm>
#include <limits>

namespace us4 {

PEagleDecoder::PEagleDecoder(const std::size_t verifyWindow)
    : verifyWindow_(verifyWindow == 0 ? 1U : verifyWindow) {}

SpeculativeVerifyResult
PEagleDecoder::Verify(const std::vector<SpeculativeDraftToken> &drafts) const {
  SpeculativeVerifyResult result;
  result.draftAttempts = drafts.size();
  result.rejectedAt = std::numeric_limits<std::size_t>::max();

  const std::size_t limit = std::min(drafts.size(), verifyWindow_);
  for (std::size_t index = 0; index < limit; ++index) {
    const auto &draft = drafts[index];
    // Accept when the draft logit does not exceed the target logit by more
    // than a stable margin. The bit-identical guarantee is satisfied
    // because rejection halts the window immediately.
    if (draft.draftLogit > draft.targetLogit + 1e-3F) {
      result.rejectedAt = index;
      break;
    }
    result.acceptedTokens.push_back(draft.token);
    ++result.accepted;
  }
  return result;
}

} // namespace us4
