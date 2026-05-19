#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>

namespace us4 {

struct SessionState {
  std::string sessionId;
  std::string kvNamespace;
  std::size_t generation = 0U;
  std::string lastPromptPrefix;
};

class SessionPool {
public:
  SessionState &Acquire(std::string sessionId);
  bool Release(const std::string &sessionId);
  std::optional<SessionState> Lookup(const std::string &sessionId) const;
  std::string NamespacedKvKey(const std::string &sessionId,
                              const std::string &logicalKey);
  std::string NamespacedPrefixKey(const std::string &sessionId,
                                  const std::string &prefix);
  void RecordPromptPrefix(const std::string &sessionId, std::string prefix);
  std::size_t ActiveSessionCount() const;

private:
  static std::string BuildKvNamespace(const std::string &sessionId);

  std::unordered_map<std::string, SessionState> sessions_;
};

} // namespace us4
