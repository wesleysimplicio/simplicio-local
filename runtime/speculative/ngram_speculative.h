#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace us4 {

struct NgramPromptLookupConfig {
  std::size_t ngramSize = 2;
  std::size_t maxDraftTokens = 4;
};

struct NgramPromptLookupResult {
  std::vector<int> tokens;
  std::size_t matchedPosition = 0;
  bool supported = false;
  std::string reason;
};

struct NgramPromptLookupBackendCapability {
  std::string backend;
  std::string version;
  bool supported = false;
  std::string reason;
};

// Backend support is opt-in. The caller must pass an explicit probe result;
// backend names and versions alone never imply that prompt lookup exists.
NgramPromptLookupBackendCapability DiscoverNgramPromptLookupBackend(
    std::string_view backend, std::string_view version,
    bool explicitlyAdvertised);

// Returns a deterministic continuation of the most recent earlier occurrence
// of the suffix n-gram. The current suffix itself is never used as its own
// match, and the result is bounded before any indexing occurs.
NgramPromptLookupResult BuildNgramPromptLookupDraft(
    const std::vector<int> &history, const NgramPromptLookupConfig &config);

} // namespace us4
