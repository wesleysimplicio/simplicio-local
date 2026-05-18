#include "scheduler/continuous_batcher.h"

#include <algorithm>
#include <unordered_set>
#include <utility>

namespace us4 {

ContinuousBatcher::ContinuousBatcher(const std::size_t fairnessQuantum)
    : fairnessQuantum_(fairnessQuantum == 0 ? 1U : fairnessQuantum) {}

void ContinuousBatcher::Submit(SessionTokenRequest request) {
  queue_.push_back(std::move(request));
}

std::optional<SessionTokenRequest> ContinuousBatcher::NextToken() {
  if (queue_.empty()) {
    return std::nullopt;
  }

  // Single-session shortcut: FIFO.
  if (queue_.size() == 1U) {
    auto request = queue_.front();
    queue_.pop_front();
    lastSession_ = request.sessionId;
    lastSessionRun_ = 1U;
    return request;
  }

  // Look for a request from a different session if the current one already
  // exhausted its quantum.
  if (!lastSession_.empty() && lastSessionRun_ >= fairnessQuantum_) {
    for (auto it = queue_.begin(); it != queue_.end(); ++it) {
      if (it->sessionId != lastSession_) {
        auto request = std::move(*it);
        queue_.erase(it);
        lastSession_ = request.sessionId;
        lastSessionRun_ = 1U;
        return request;
      }
    }
  }

  auto request = queue_.front();
  queue_.pop_front();
  if (request.sessionId == lastSession_) {
    ++lastSessionRun_;
  } else {
    lastSession_ = request.sessionId;
    lastSessionRun_ = 1U;
  }
  return request;
}

std::size_t ContinuousBatcher::QueueSize() const { return queue_.size(); }

std::vector<std::string> ContinuousBatcher::ActiveSessions() const {
  std::unordered_set<std::string> seen;
  std::vector<std::string> result;
  for (const auto &request : queue_) {
    if (seen.insert(request.sessionId).second) {
      result.push_back(request.sessionId);
    }
  }
  return result;
}

} // namespace us4
