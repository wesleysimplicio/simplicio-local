#include "tuning/profile_cache.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <sstream>
#include <string_view>
#include <vector>

namespace us4 {

bool operator==(const ProfileCacheKey &lhs, const ProfileCacheKey &rhs) {
  return lhs.chip == rhs.chip && lhs.modelId == rhs.modelId &&
         lhs.hardwareFingerprint == rhs.hardwareFingerprint &&
         lhs.isa == rhs.isa && lhs.backend == rhs.backend &&
         lhs.modelDigest == rhs.modelDigest && lhs.operation == rhs.operation &&
         lhs.dtype == rhs.dtype && lhs.shapeClass == rhs.shapeClass &&
         lhs.runtimeVersion == rhs.runtimeVersion &&
         lhs.kernelVersion == rhs.kernelVersion &&
         lhs.layoutVersion == rhs.layoutVersion;
}

std::size_t
ProfileCacheKeyHash::operator()(const ProfileCacheKey &key) const noexcept {
  const std::size_t chipHash = std::hash<std::string>{}(key.chip);
  const std::size_t modelHash = std::hash<std::string>{}(key.modelId);
  std::size_t result = chipHash ^ (modelHash * 131U);
  const std::string fingerprint = key.hardwareFingerprint + key.isa + key.backend +
                                  key.modelDigest + key.operation + key.dtype +
                                  key.shapeClass + key.runtimeVersion +
                                  key.kernelVersion + key.layoutVersion;
  result ^= std::hash<std::string>{}(fingerprint) * 17U;
  return result;
}

void ProfileCache::Store(const ProfileCacheKey &key,
                         const AutoTunerProfile &profile) {
  profiles_[key] = profile;
}

std::optional<AutoTunerProfile>
ProfileCache::Lookup(const ProfileCacheKey &key) const {
  const auto it = profiles_.find(key);
  if (it == profiles_.end()) {
    return std::nullopt;
  }
  return it->second;
}

std::size_t ProfileCache::Size() const { return profiles_.size(); }

std::string ProfileCache::Serialize() const {
  std::vector<std::pair<ProfileCacheKey, AutoTunerProfile>> entries(
      profiles_.begin(), profiles_.end());
  std::sort(entries.begin(), entries.end(),
            [](const std::pair<ProfileCacheKey, AutoTunerProfile> &lhs,
               const std::pair<ProfileCacheKey, AutoTunerProfile> &rhs) {
              if (lhs.first.chip != rhs.first.chip) {
                return lhs.first.chip < rhs.first.chip;
              }
              return lhs.first.modelId < rhs.first.modelId;
            });
  std::ostringstream stream;
  for (const auto &entry : entries) {
    stream << "chip=" << entry.first.chip
           << ";model=" << entry.first.modelId
           << ";hardware=" << entry.first.hardwareFingerprint
           << ";isa=" << entry.first.isa
           << ";backend=" << entry.first.backend
           << ";model_digest=" << entry.first.modelDigest
           << ";operation=" << entry.first.operation
           << ";dtype=" << entry.first.dtype
           << ";shape=" << entry.first.shapeClass
           << ";runtime=" << entry.first.runtimeVersion
           << ";kernel=" << entry.first.kernelVersion
           << ";layout=" << entry.first.layoutVersion
           << ";tile_rows=" << entry.second.tileRows
           << ";tile_cols=" << entry.second.tileCols
           << ";batch=" << entry.second.batchSize
           << ";latency_ms=" << entry.second.estimatedLatencyMs
           << ";speculative_lookahead="
           << entry.second.speculativeLookaheadTokens
           << ";speculative_warmup=" << entry.second.speculativeWarmupRuns
           << ";learned_pins=" << entry.second.learnedPinnedExperts << "\n";
  }
  return stream.str();
}

bool ProfileCache::Load(const std::string &body) {
  std::istringstream stream(body);
  std::string line;
  std::unordered_map<ProfileCacheKey, AutoTunerProfile, ProfileCacheKeyHash>
      next;
  while (std::getline(stream, line)) {
    if (line.empty() || line.front() == '#') {
      continue;
    }
    ProfileCacheKey key;
    AutoTunerProfile profile;
    std::istringstream parts(line);
    std::string part;
    while (std::getline(parts, part, ';')) {
      const auto eq = part.find('=');
      if (eq == std::string::npos) {
        continue;
      }
      const std::string name = part.substr(0, eq);
      const std::string value = part.substr(eq + 1);
      if (name == "chip") {
        key.chip = value;
        profile.chip = value;
      } else if (name == "model") {
        key.modelId = value;
      } else if (name == "hardware") {
        key.hardwareFingerprint = value;
      } else if (name == "isa") {
        key.isa = value;
      } else if (name == "backend") {
        key.backend = value;
      } else if (name == "model_digest") {
        key.modelDigest = value;
      } else if (name == "operation") {
        key.operation = value;
      } else if (name == "dtype") {
        key.dtype = value;
      } else if (name == "shape") {
        key.shapeClass = value;
      } else if (name == "runtime") {
        key.runtimeVersion = value;
      } else if (name == "kernel") {
        key.kernelVersion = value;
      } else if (name == "layout") {
        key.layoutVersion = value;
      } else if (name == "tile_rows") {
        profile.tileRows = static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      } else if (name == "tile_cols") {
        profile.tileCols = static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      } else if (name == "batch") {
        profile.batchSize = static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      } else if (name == "latency_ms") {
        profile.estimatedLatencyMs = std::strtof(value.c_str(), nullptr);
      } else if (name == "speculative_lookahead") {
        profile.speculativeLookaheadTokens =
            static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      } else if (name == "speculative_warmup") {
        profile.speculativeWarmupRuns =
            static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      } else if (name == "learned_pins") {
        profile.learnedPinnedExperts =
            static_cast<std::size_t>(std::strtoul(value.c_str(), nullptr, 10));
      }
    }
    if (key.chip.empty() || key.modelId.empty()) {
      return false;
    }
    next[key] = profile;
  }
  profiles_ = std::move(next);
  return true;
}

bool ProfileCache::SaveAtomic(const std::string &path) const {
  const std::filesystem::path destination(path);
  const std::filesystem::path temporary = destination.string() + ".tmp";
  std::ofstream stream(temporary, std::ios::out | std::ios::trunc);
  if (!stream) {
    return false;
  }
  stream << Serialize();
  stream.flush();
  if (!stream) {
    stream.close();
    std::error_code ignored;
    std::filesystem::remove(temporary, ignored);
    return false;
  }
  stream.close();
  std::error_code error;
  std::filesystem::rename(temporary, destination, error);
  if (error) {
    std::filesystem::remove(destination, error);
    error.clear();
    std::filesystem::rename(temporary, destination, error);
  }
  if (error) {
    std::filesystem::remove(temporary, error);
    return false;
  }
  return true;
}

bool ProfileCache::LoadFile(const std::string &path) {
  std::ifstream stream(path);
  if (!stream) {
    return false;
  }
  std::ostringstream body;
  body << stream.rdbuf();
  return Load(body.str());
}

} // namespace us4
