#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// SparsityAwareCache keeps a small map keyed by the expert pattern hash that
// produced a given output. Adapters can use this to short-circuit repeated
// computation when the same routing pattern shows up across the prompt.

struct SparsityCacheEntry {
  std::string patternHash;
  std::vector<float> activation;
  std::size_t hitCount = 0;
};

class SparsityAwareCache {
 public:
  explicit SparsityAwareCache(std::size_t capacity = 16);

  void Store(std::string patternHash, std::vector<float> activation);
  std::optional<std::vector<float>> Lookup(const std::string& patternHash);
  std::size_t EntryCount() const;
  std::size_t HitCount() const { return totalHits_; }
  std::size_t MissCount() const { return totalMisses_; }
  float HitRatio() const;

 private:
  std::size_t capacity_;
  std::unordered_map<std::string, SparsityCacheEntry> entries_;
  std::size_t totalHits_ = 0;
  std::size_t totalMisses_ = 0;
};

}  // namespace us4
