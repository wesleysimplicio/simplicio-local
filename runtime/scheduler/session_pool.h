#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// SessionPool keeps per-session KV state under namespaces that never leak.
// The pool is intentionally minimal; it owns the lifecycle plus the
// namespace string so adapters can hand off the right context to KvPager.

struct SessionContext {
  std::string sessionId;
  std::string kvNamespace;
  std::vector<float> rollingContext;
};

class SessionPool {
 public:
  SessionContext& GetOrCreate(const std::string& sessionId);
  std::optional<SessionContext> Snapshot(const std::string& sessionId) const;
  void AppendRollingContext(const std::string& sessionId,
                            const std::vector<float>& tokens);
  void Drop(const std::string& sessionId);
  std::size_t Size() const;

 private:
  std::unordered_map<std::string, SessionContext> sessions_;
};

}  // namespace us4
