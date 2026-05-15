#pragma once

namespace us4 {

class ScopedAutoreleasePool {
 public:
  ScopedAutoreleasePool();
  ~ScopedAutoreleasePool();

  bool Active() const;

 private:
  bool active_ = false;
};

}  // namespace us4
