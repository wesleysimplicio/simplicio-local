#include "scheduler/session_pool.h"

namespace us4 {

SessionState &SessionPool::Acquire(std::string sessionId) {
  auto [it, inserted] = sessions_.try_emplace(sessionId, SessionState{});
  SessionState &state = it->second;
  if (inserted) {
    state.sessionId = it->first;
    state.kvNamespace = BuildKvNamespace(state.sessionId);
    state.generation = 1U;
  }
  return state;
}

bool SessionPool::Release(const std::string &sessionId) {
  return sessions_.erase(sessionId) > 0U;
}

std::optional<SessionState>
SessionPool::Lookup(const std::string &sessionId) const {
  const auto it = sessions_.find(sessionId);
  if (it == sessions_.end()) {
    return std::nullopt;
  }
  return it->second;
}

std::string SessionPool::NamespacedKvKey(const std::string &sessionId,
                                         const std::string &logicalKey) {
  const SessionState &state = Acquire(sessionId);
  return state.kvNamespace + "::kv::" + logicalKey;
}

std::string SessionPool::NamespacedPrefixKey(const std::string &sessionId,
                                             const std::string &prefix) {
  const SessionState &state = Acquire(sessionId);
  return state.kvNamespace + "::prefix::" + prefix;
}

void SessionPool::RecordPromptPrefix(const std::string &sessionId,
                                     std::string prefix) {
  SessionState &state = Acquire(sessionId);
  state.lastPromptPrefix = std::move(prefix);
}

std::size_t SessionPool::ActiveSessionCount() const { return sessions_.size(); }

std::string SessionPool::BuildKvNamespace(const std::string &sessionId) {
  return "session::" + sessionId;
}

} // namespace us4
