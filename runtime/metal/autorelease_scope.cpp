#include "metal/autorelease_scope.h"

namespace us4 {

ScopedAutoreleasePool::ScopedAutoreleasePool() = default;

ScopedAutoreleasePool::~ScopedAutoreleasePool() = default;

bool ScopedAutoreleasePool::Active() const { return active_; }

}  // namespace us4
