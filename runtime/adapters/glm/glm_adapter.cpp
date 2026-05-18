#include "adapters/glm/glm_adapter.h"

namespace us4 {

GlmAdapter::GlmAdapter() : DenseAdapterBase("glm", "glm-4-moe") {}

ArchitectureType GlmAdapter::Architecture() const {
  return ArchitectureType::kMoE;
}

bool GlmAdapter::SupportsMoe() const { return true; }

std::uint32_t GlmAdapter::Seed() const { return 47711U; }

std::vector<std::string> GlmAdapter::Vocabulary() const {
  return {"glm",   "moe",      "router",  "expert",  "shared", "routed",
          "apple", "runtime",  "responds", "with",   "sparsity",
          "aware", "cache",    "hi",       ".",       "stable"};
}

std::string GlmAdapter::DefaultPromptToken() const { return "hi"; }

}  // namespace us4
