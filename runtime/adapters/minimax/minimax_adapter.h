#pragma once

#include <cstddef>
#include <string_view>

#include "adapters/dense_adapter_base.h"

namespace us4 {

class MiniMaxAdapter final : public DenseAdapterBase {
 public:
  MiniMaxAdapter();

  ArchitectureType Architecture() const override;
  bool SupportsMoe() const override;

  static constexpr std::string_view kFamily = "minimax";
  static constexpr std::string_view kDefaultModel = "minimax-m2";

 protected:
  std::uint32_t Seed() const override;
  std::vector<std::string> Vocabulary() const override;
  std::string DefaultPromptToken() const override;
};

}  // namespace us4
