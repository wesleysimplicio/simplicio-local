#include "core/kernel_registry.h"

#include <algorithm>
#include <set>

namespace us4 {

std::string_view ToString(const KernelOperation operation) {
  switch (operation) {
    case KernelOperation::kInt8Matmul:
      return "int8-matmul";
    case KernelOperation::kFloatMatmul:
      return "float-matmul";
    case KernelOperation::kRmsNorm:
      return "rmsnorm";
    case KernelOperation::kRope:
      return "rope";
    case KernelOperation::kSoftmax:
      return "softmax";
  }
  return "unknown";
}

namespace {

bool IsUsable(const KernelImplementation& implementation,
              const KernelOperation operation,
              const std::vector<std::string>& detected_isa) {
  if (!implementation.descriptor.compiled ||
      implementation.descriptor.operation != operation) {
    return false;
  }
  if (operation == KernelOperation::kInt8Matmul &&
      implementation.int8_matmul == nullptr) {
    return false;
  }
  if (operation == KernelOperation::kFloatMatmul &&
      implementation.float_matmul == nullptr) {
    return false;
  }
  const std::set<std::string> available(detected_isa.begin(), detected_isa.end());
  return std::all_of(
      implementation.descriptor.isa_requirements.begin(),
      implementation.descriptor.isa_requirements.end(),
      [&available](const std::string& feature) {
        return available.find(feature) != available.end();
      });
}

}  // namespace

bool KernelRegistry::Register(KernelImplementation implementation) {
  if (implementation.descriptor.name.empty() ||
      Find(implementation.descriptor.name) != nullptr) {
    return false;
  }
  if (implementation.descriptor.portable &&
      !implementation.descriptor.isa_requirements.empty()) {
    return false;
  }
  implementations_.push_back(std::move(implementation));
  return true;
}

const KernelImplementation* KernelRegistry::Find(
    const std::string_view name) const {
  const auto it = std::find_if(
      implementations_.begin(), implementations_.end(),
      [name](const KernelImplementation& implementation) {
        return implementation.descriptor.name == name;
      });
  return it == implementations_.end() ? nullptr : &*it;
}

KernelSelection KernelRegistry::Select(
    const KernelOperation operation, const std::string_view requested_kernel,
    const std::vector<std::string>& detected_isa,
    const bool force_scalar) const {
  KernelSelection selection{.requested_kernel = std::string(requested_kernel),
                            .effective_kernel = "scalar",
                            .isa = detected_isa.empty() ? "none"
                                                         : detected_isa.front(),
                            .fallback = true,
                            .reason = "portable scalar fallback"};
  const KernelImplementation* scalar = nullptr;
  for (const auto& implementation : implementations_) {
    if (implementation.descriptor.operation == operation &&
        implementation.descriptor.portable &&
        IsUsable(implementation, operation, detected_isa)) {
      scalar = &implementation;
      break;
    }
  }
  selection.implementation = scalar;

  if (force_scalar) {
    selection.reason = "scalar forced by runtime kill switch";
    return selection;
  }

  const KernelImplementation* requested = Find(requested_kernel);
  if (requested != nullptr &&
      IsUsable(*requested, operation, detected_isa)) {
    selection.effective_kernel = requested->descriptor.name;
    selection.fallback = false;
    selection.reason = "requested kernel capability and function pointer passed";
    selection.implementation = requested;
    return selection;
  }

  const KernelImplementation* best = nullptr;
  for (const auto& implementation : implementations_) {
    if (!IsUsable(implementation, operation, detected_isa) ||
        implementation.descriptor.portable) {
      continue;
    }
    if (best == nullptr || implementation.descriptor.priority >
                               best->descriptor.priority) {
      best = &implementation;
    }
  }
  if (best != nullptr) {
    selection.effective_kernel = best->descriptor.name;
    selection.fallback = false;
    selection.reason = requested_kernel.empty()
                           ? "best compiled kernel selected"
                           : "requested kernel unavailable; best compiled kernel selected";
    selection.implementation = best;
  } else if (!requested_kernel.empty()) {
    selection.reason = "requested kernel unavailable; portable scalar fallback";
  }
  return selection;
}

std::vector<KernelDescriptor> KernelRegistry::Catalog() const {
  std::vector<KernelDescriptor> result;
  result.reserve(implementations_.size());
  for (const auto& implementation : implementations_) {
    result.push_back(implementation.descriptor);
  }
  std::sort(result.begin(), result.end(),
            [](const KernelDescriptor& lhs, const KernelDescriptor& rhs) {
              return lhs.name < rhs.name;
            });
  return result;
}

std::size_t KernelRegistry::Size() const { return implementations_.size(); }

}  // namespace us4
