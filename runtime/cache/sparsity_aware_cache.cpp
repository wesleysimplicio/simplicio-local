#include "cache/sparsity_aware_cache.h"

#include <algorithm>
#include <utility>

namespace us4 {

SparsityAwareCache::SparsityAwareCache(const std::size_t capacity)
    : capacity_(capacity == 0 ? 1U : capacity) {}

void SparsityAwareCache::Store(std::string patternHash,
                               std::vector<float> activation) {
  if (entries_.size() >= capacity_ && entries_.find(patternHash) == entries_.end()) {
    // Evict the least-hit entry; deterministic tiebreak by hash string.
    auto victim = entries_.begin();
    for (auto it = entries_.begin(); it != entries_.end(); ++it) {
      if (it->second.hitCount < victim->second.hitCount ||
          (it->second.hitCount == victim->second.hitCount &&
           it->first < victim->first)) {
        victim = it;
      }
    }
    if (victim != entries_.end()) {
      entries_.erase(victim);
    }
  }
  SparsityCacheEntry entry;
  entry.patternHash = patternHash;
  entry.activation = std::move(activation);
  entries_[std::move(patternHash)] = std::move(entry);
}

std::optional<std::vector<float>>
SparsityAwareCache::Lookup(const std::string &patternHash) {
  const auto it = entries_.find(patternHash);
  if (it == entries_.end()) {
    ++totalMisses_;
    return std::nullopt;
  }
  ++it->second.hitCount;
  ++totalHits_;
  return it->second.activation;
}

std::size_t SparsityAwareCache::EntryCount() const { return entries_.size(); }

float SparsityAwareCache::HitRatio() const {
  const std::size_t total = totalHits_ + totalMisses_;
  if (total == 0) {
    return 0.0F;
  }
  return static_cast<float>(totalHits_) / static_cast<float>(total);
}

} // namespace us4
