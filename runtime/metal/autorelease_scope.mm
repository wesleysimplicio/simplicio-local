#include "metal/autorelease_scope.h"

#import <Foundation/Foundation.h>

namespace us4 {

std::string_view ToString(const AutoreleaseBoundaryKind kind) {
  switch (kind) {
  case AutoreleaseBoundaryKind::kNoop:
    return "noop";
  case AutoreleaseBoundaryKind::kObjectiveC:
    return "objective-c-autorelease";
  }
  return "noop";
}

ScopedAutoreleasePool::ScopedAutoreleasePool(const bool requested)
    : requested_(requested) {
  if (requested_) {
    pool_ = (void *)[[NSAutoreleasePool alloc] init];
    active_ = pool_ != nullptr;
    kind_ = active_ ? AutoreleaseBoundaryKind::kObjectiveC
                    : AutoreleaseBoundaryKind::kNoop;
  }
}

ScopedAutoreleasePool::~ScopedAutoreleasePool() {
  if (pool_ != nullptr) {
    [(NSAutoreleasePool *)pool_ drain];
  }
}

bool ScopedAutoreleasePool::Requested() const { return requested_; }

bool ScopedAutoreleasePool::Active() const { return active_; }

AutoreleaseBoundaryKind ScopedAutoreleasePool::Kind() const { return kind_; }

} // namespace us4
