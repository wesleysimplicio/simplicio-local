#pragma once

#include <cstddef>
#include <deque>
#include <optional>
#include <string>
#include <vector>

namespace us4 {

// Continuous batcher: round-robin across active sessions while honouring a
// per-session quantum so heavy prompts cannot starve interactive ones.
//
// Contract guarantees:
// - tokens admitted from session N go to the same output channel as long as
//   the session is registered;
// - the next token always comes from a different session than the previous
//   one when more than one session has work pending;
// - single-session use degrades to a simple FIFO and stays compatible with
//   the existing adapter API.

struct SessionTokenRequest {
  std::string sessionId;
  std::string prompt;
};

class ContinuousBatcher {
 public:
  explicit ContinuousBatcher(std::size_t fairnessQuantum = 1);

  void Submit(SessionTokenRequest request);
  std::optional<SessionTokenRequest> NextToken();
  std::size_t QueueSize() const;
  std::vector<std::string> ActiveSessions() const;

 private:
  std::size_t fairnessQuantum_;
  std::size_t cursor_ = 0;
  std::size_t lastSessionRun_ = 0;
  std::string lastSession_;
  std::deque<SessionTokenRequest> queue_;
};

}  // namespace us4
