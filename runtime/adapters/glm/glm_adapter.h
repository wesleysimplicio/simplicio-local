#pragma once

#include <cstddef>
#include <string_view>

#include "adapters/dense_adapter_base.h"

namespace us4 {

class GlmAdapter final : public DenseAdapterBase {
 public:
  GlmAdapter();

  ArchitectureType Architecture() const override;
  bool SupportsMoe() const override;

  static constexpr std::string_view kFamily = "glm";
  static constexpr std::string_view kDefaultModel = "glm-4-moe";

 protected:
  std::uint32_t Seed() const override;
  std::vector<std::string> Vocabulary() const override;
  std::string DefaultPromptToken() const override;
};

}  // namespace us4
