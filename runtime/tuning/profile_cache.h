#pragma once

#include <optional>
#include <string>
#include <unordered_map>

#include "tuning/auto_tuner.h"

namespace us4 {

// ProfileCache persists the auto-tuner decision so we don't run the
// mini-bench on every startup. The contract is small: lookup by chip +
// model id, store the chosen profile, serialise to a deterministic body
// for `runtime/tuning/profiles.json`.

struct ProfileCacheKey {
  std::string chip;
  std::string modelId;
  std::string hardwareFingerprint;
  std::string isa;
  std::string backend;
  std::string modelDigest;
  std::string operation;
  std::string dtype;
  std::string shapeClass;
  std::string runtimeVersion;
  std::string kernelVersion;
  std::string layoutVersion;
};

bool operator==(const ProfileCacheKey& lhs, const ProfileCacheKey& rhs);

struct ProfileCacheKeyHash {
  std::size_t operator()(const ProfileCacheKey& key) const noexcept;
};

class ProfileCache {
 public:
  void Store(const ProfileCacheKey& key, const AutoTunerProfile& profile);
  std::optional<AutoTunerProfile> Lookup(const ProfileCacheKey& key) const;
  std::size_t Size() const;
  std::string Serialize() const;
  bool Load(const std::string& body);
  bool SaveAtomic(const std::string& path) const;
  bool LoadFile(const std::string& path);

 private:
  std::unordered_map<ProfileCacheKey, AutoTunerProfile, ProfileCacheKeyHash>
      profiles_;
};

}  // namespace us4
