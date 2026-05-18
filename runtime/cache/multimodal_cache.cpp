#include "cache/multimodal_cache.h"

#include <functional>
#include <utility>

namespace us4 {

bool operator==(const MultimodalCacheKey &lhs, const MultimodalCacheKey &rhs) {
  return lhs.assetHash == rhs.assetHash && lhs.modality == rhs.modality &&
         lhs.tileIndex == rhs.tileIndex;
}

std::size_t MultimodalCacheKeyHash::operator()(const MultimodalCacheKey &key) const noexcept {
  const std::size_t assetHash = std::hash<std::string>{}(key.assetHash);
  const std::size_t modalityHash =
      std::hash<int>{}(static_cast<int>(key.modality));
  const std::size_t tileHash = std::hash<std::size_t>{}(key.tileIndex);
  return assetHash ^ (modalityHash * 31U) ^ (tileHash * 131U);
}

void MultimodalCache::Store(MultimodalCacheKey key, std::vector<float> tokens) {
  MultimodalCacheEntry entry;
  entry.tokens = std::move(tokens);
  entries_[std::move(key)] = std::move(entry);
}

std::optional<std::vector<float>>
MultimodalCache::Lookup(const MultimodalCacheKey &key) {
  const auto it = entries_.find(key);
  if (it == entries_.end()) {
    ++misses_;
    return std::nullopt;
  }
  ++it->second.hitCount;
  ++hits_;
  return it->second.tokens;
}

std::size_t MultimodalCache::EntryCount() const { return entries_.size(); }

} // namespace us4
