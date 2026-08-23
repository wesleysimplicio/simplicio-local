#include "speculative/ngram_speculative.h"

#include <algorithm>

namespace us4 {

NgramPromptLookupBackendCapability DiscoverNgramPromptLookupBackend(
    const std::string_view backend, const std::string_view version,
    const bool explicitlyAdvertised) {
  NgramPromptLookupBackendCapability result;
  result.backend = std::string(backend);
  result.version = std::string(version);
  if (backend.empty()) {
    result.reason = "backend-unknown";
  } else if (!explicitlyAdvertised) {
    result.reason = "backend-did-not-advertise-prompt-lookup";
  } else {
    result.supported = true;
    result.reason = "explicit-backend-capability";
  }
  return result;
}

NgramPromptLookupResult BuildNgramPromptLookupDraft(
    const std::vector<int> &history, const NgramPromptLookupConfig &config) {
  NgramPromptLookupResult result;
  if (config.ngramSize == 0 || config.maxDraftTokens == 0) {
    result.reason = "invalid-zero-sized-config";
    return result;
  }
  if (history.size() <= config.ngramSize) {
    result.reason = "history-too-short";
    return result;
  }

  const std::size_t suffixStart = history.size() - config.ngramSize;
  // Search backwards so repeated patterns choose the nearest proven context.
  for (std::size_t candidate = suffixStart; candidate-- > 0;) {
    if (!std::equal(history.begin() +
                        static_cast<std::ptrdiff_t>(candidate),
                    history.begin() + static_cast<std::ptrdiff_t>(candidate) +
                        static_cast<std::ptrdiff_t>(config.ngramSize),
                    history.begin() + static_cast<std::ptrdiff_t>(suffixStart))) {
      continue;
    }
    const std::size_t continuationStart = candidate + config.ngramSize;
    if (continuationStart >= suffixStart) {
      continue;
    }
    const std::size_t continuationCount = std::min(
        config.maxDraftTokens, suffixStart - continuationStart);
    result.tokens.assign(
        history.begin() + static_cast<std::ptrdiff_t>(continuationStart),
        history.begin() + static_cast<std::ptrdiff_t>(continuationStart +
                                                        continuationCount));
    if (!result.tokens.empty()) {
      result.supported = true;
      result.matchedPosition = candidate;
      result.reason = "prompt-lookup-match";
      return result;
    }
  }
  result.reason = "no-earlier-ngram-match";
  return result;
}

} // namespace us4
