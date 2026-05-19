#pragma once

#include <cstddef>
#include <vector>

#include "core/runtime_mode.h"

namespace us4 {

struct TelemetrySnapshot {
  double latencyMs = 0.0;
  double tokensPerSecond = 0.0;
  unsigned long long peakMemoryGiB = 0;
  std::size_t promptTokens = 0;
  std::size_t generatedTokens = 0;
  RuntimeMode mode = RuntimeMode::kNano;
  std::size_t moeSelectedExperts = 0;
  double moeRouterEntropy = 0.0;
  std::size_t moePagerLoads = 0;
  std::size_t moePagerEvictions = 0;
  std::size_t moePagerReuses = 0;
  std::size_t moeSparsityCacheHits = 0;
  std::size_t moeSparsityCacheMisses = 0;
  std::size_t multimodalCacheHits = 0;
  std::size_t multimodalCacheMisses = 0;

  bool HasMoeTelemetry() const {
    return moeSelectedExperts > 0 || moeRouterEntropy > 0.0 ||
           moePagerLoads > 0 || moePagerEvictions > 0 || moePagerReuses > 0 ||
           moeSparsityCacheHits > 0 || moeSparsityCacheMisses > 0 ||
           multimodalCacheHits > 0 || multimodalCacheMisses > 0;
  }

  double MoeHitRate() const {
    const std::size_t denominator = moePagerLoads + moePagerReuses;
    if (denominator == 0U) {
      return 0.0;
    }
    return static_cast<double>(moePagerReuses) /
           static_cast<double>(denominator);
  }

  double MoeEvictionRate() const {
    const std::size_t denominator = moePagerLoads + moePagerReuses;
    if (denominator == 0U) {
      return 0.0;
    }
    return static_cast<double>(moePagerEvictions) /
           static_cast<double>(denominator);
  }

  double MoeSparsityCacheHitRatio() const {
    const std::size_t denominator =
        moeSparsityCacheHits + moeSparsityCacheMisses;
    if (denominator == 0U) {
      return 0.0;
    }
    return static_cast<double>(moeSparsityCacheHits) /
           static_cast<double>(denominator);
  }

  double MultimodalCacheHitRatio() const {
    const std::size_t denominator = multimodalCacheHits + multimodalCacheMisses;
    if (denominator == 0U) {
      return 0.0;
    }
    return static_cast<double>(multimodalCacheHits) /
           static_cast<double>(denominator);
  }
};

class TelemetrySink {
public:
  void Record(const TelemetrySnapshot &snapshot);
  const std::vector<TelemetrySnapshot> &Snapshots() const;
  bool Empty() const;

private:
  std::vector<TelemetrySnapshot> snapshots_;
};

} // namespace us4
