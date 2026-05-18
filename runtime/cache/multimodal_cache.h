#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// Multimodal cache keeps image patch tokens and audio frame embeddings keyed
// by a stable asset hash + tile id. Dense-only adapters never touch this
// cache; it stays isolated through its own namespace.

enum class MultimodalModality {
  kImage,
  kAudio,
};

struct MultimodalCacheKey {
  std::string assetHash;
  MultimodalModality modality = MultimodalModality::kImage;
  std::size_t tileIndex = 0;
};

struct MultimodalCacheEntry {
  std::vector<float> tokens;
  std::size_t hitCount = 0;
};

bool operator==(const MultimodalCacheKey& lhs, const MultimodalCacheKey& rhs);

struct MultimodalCacheKeyHash {
  std::size_t operator()(const MultimodalCacheKey& key) const noexcept;
};

class MultimodalCache {
 public:
  void Store(MultimodalCacheKey key, std::vector<float> tokens);
  std::optional<std::vector<float>> Lookup(const MultimodalCacheKey& key);
  std::size_t EntryCount() const;
  std::size_t HitCount() const { return hits_; }
  std::size_t MissCount() const { return misses_; }

 private:
  std::unordered_map<MultimodalCacheKey, MultimodalCacheEntry,
                     MultimodalCacheKeyHash> entries_;
  std::size_t hits_ = 0;
  std::size_t misses_ = 0;
};

}  // namespace us4
