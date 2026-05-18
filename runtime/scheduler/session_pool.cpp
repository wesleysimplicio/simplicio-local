#include "scheduler/session_pool.h"

namespace us4 {

SessionContext &SessionPool::GetOrCreate(const std::string &sessionId) {
  auto it = sessions_.find(sessionId);
  if (it != sessions_.end()) {
    return it->second;
  }
  SessionContext context;
  context.sessionId = sessionId;
  context.kvNamespace = "session::" + sessionId;
  sessions_[sessionId] = std::move(context);
  return sessions_[sessionId];
}

std::optional<SessionContext>
SessionPool::Snapshot(const std::string &sessionId) const {
  const auto it = sessions_.find(sessionId);
  if (it == sessions_.end()) {
    return std::nullopt;
  }
  return it->second;
}

void SessionPool::AppendRollingContext(const std::string &sessionId,
                                       const std::vector<float> &tokens) {
  auto &context = GetOrCreate(sessionId);
  context.rollingContext.insert(context.rollingContext.end(), tokens.begin(),
                                tokens.end());
}

void SessionPool::Drop(const std::string &sessionId) {
  sessions_.erase(sessionId);
}

std::size_t SessionPool::Size() const { return sessions_.size(); }

} // namespace us4
