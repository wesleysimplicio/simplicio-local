#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace us4 {

struct ModalityTokenState {
  std::string modality;
  std::vector<std::string> tokens;
};

struct MultimodalCacheEntry {
  std::string family;
  std::string modality;
  std::string key;
  std::size_t tokenCount = 0;
  std::size_t uses = 0;
  std::size_t hits = 0;
};

struct MultimodalCacheSnapshot {
  std::size_t entryCount = 0;
  std::size_t hitCount = 0;
  std::size_t missCount = 0;
  double hitRatio = 0.0;
  std::size_t lastTouchHits = 0;
  std::size_t lastTouchMisses = 0;
  std::size_t activeModalities = 0;
  std::vector<std::string> lastModalities;
};

class MultimodalCache {
public:
  MultimodalCacheSnapshot Touch(std::string_view family,
                                const std::vector<ModalityTokenState> &states);
  std::size_t EntryCount() const;

private:
  static std::size_t ComputeTokenHash(const std::vector<std::string> &tokens);
  static std::string BuildKey(std::string_view family,
                              std::string_view modality, std::size_t tokenHash);
  MultimodalCacheSnapshot
  Snapshot(std::size_t lastTouchHits, std::size_t lastTouchMisses,
           std::vector<std::string> lastModalities) const;

  std::unordered_map<std::string, MultimodalCacheEntry> entries_;
  std::size_t hitCount_ = 0;
  std::size_t missCount_ = 0;
};

} // namespace us4
