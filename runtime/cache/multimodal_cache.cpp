#include "cache/multimodal_cache.h"

#include <utility>

namespace us4 {

namespace {

constexpr std::size_t kHashOffset = 1469598103934665603ULL;
constexpr std::size_t kHashPrime = 1099511628211ULL;

} // namespace

MultimodalCacheSnapshot
MultimodalCache::Touch(const std::string_view family,
                       const std::vector<ModalityTokenState> &states) {
  std::size_t lastTouchHits = 0;
  std::size_t lastTouchMisses = 0;
  std::vector<std::string> lastModalities;
  lastModalities.reserve(states.size());

  for (const ModalityTokenState &state : states) {
    const std::size_t tokenHash = ComputeTokenHash(state.tokens);
    const std::string key = BuildKey(family, state.modality, tokenHash);
    lastModalities.push_back(state.modality);
    const auto it = entries_.find(key);
    if (it != entries_.end()) {
      ++hitCount_;
      ++lastTouchHits;
      ++it->second.uses;
      ++it->second.hits;
      continue;
    }

    ++missCount_;
    ++lastTouchMisses;
    MultimodalCacheEntry entry;
    entry.family = std::string(family);
    entry.modality = state.modality;
    entry.key = key;
    entry.tokenCount = state.tokens.size();
    entry.uses = 1U;
    entries_.emplace(key, std::move(entry));
  }

  return Snapshot(lastTouchHits, lastTouchMisses, std::move(lastModalities));
}

std::size_t MultimodalCache::EntryCount() const { return entries_.size(); }

std::size_t
MultimodalCache::ComputeTokenHash(const std::vector<std::string> &tokens) {
  std::size_t hash = kHashOffset;
  for (const std::string &token : tokens) {
    for (const unsigned char ch : token) {
      hash ^= ch;
      hash *= kHashPrime;
    }
    hash ^= 0xFFU;
    hash *= kHashPrime;
  }
  return hash;
}

std::string MultimodalCache::BuildKey(const std::string_view family,
                                      const std::string_view modality,
                                      const std::size_t tokenHash) {
  std::string key(family);
  key += ":";
  key += modality;
  key += ":";
  key += std::to_string(tokenHash);
  return key;
}

MultimodalCacheSnapshot
MultimodalCache::Snapshot(const std::size_t lastTouchHits,
                          const std::size_t lastTouchMisses,
                          std::vector<std::string> lastModalities) const {
  MultimodalCacheSnapshot snapshot;
  snapshot.entryCount = entries_.size();
  snapshot.hitCount = hitCount_;
  snapshot.missCount = missCount_;
  const std::size_t denominator = hitCount_ + missCount_;
  snapshot.hitRatio = denominator == 0U ? 0.0
                                        : static_cast<double>(hitCount_) /
                                              static_cast<double>(denominator);
  snapshot.lastTouchHits = lastTouchHits;
  snapshot.lastTouchMisses = lastTouchMisses;
  snapshot.activeModalities = lastModalities.size();
  snapshot.lastModalities = std::move(lastModalities);
  return snapshot;
}

} // namespace us4
