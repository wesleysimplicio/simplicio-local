#include "adapters/minimax/minimax_adapter.h"

namespace us4 {

MiniMaxAdapter::MiniMaxAdapter() : DenseAdapterBase("minimax", "minimax-m2") {}

ArchitectureType MiniMaxAdapter::Architecture() const {
  return ArchitectureType::kMoE;
}

bool MiniMaxAdapter::SupportsMoe() const { return true; }

std::uint32_t MiniMaxAdapter::Seed() const { return 41011U; }

std::vector<std::string> MiniMaxAdapter::Vocabulary() const {
  return {"minimax", "moe",      "router", "expert",  "image", "audio",
          "tokens",  "multimodal", "apple",  "runtime", "responds",
          "with",     "shared",   "experts", "hi",     "."};
}

std::string MiniMaxAdapter::DefaultPromptToken() const { return "hi"; }

}  // namespace us4
