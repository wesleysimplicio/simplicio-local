#pragma once

#include "adapters/dense_adapter_base.h"

namespace us4 {

class LlamaAdapter final : public DenseAdapterBase {
public:
  LlamaAdapter();

  bool SupportsMlxBackend() const override;
  bool SupportsMetalBackend() const override;
  GenerationResult Generate(const GenerationRequest &request,
                            const RuntimeContext &context) const override;

protected:
  std::uint32_t Seed() const override;
  std::vector<std::string> Vocabulary() const override;
  std::string DefaultPromptToken() const override;

private:
  std::vector<float> BuildRopeRow(std::size_t tokenId, std::uint32_t seed,
                                  std::size_t position) const;
  std::vector<float> BuildValueRow(std::size_t tokenId, std::uint32_t seed,
                                   std::size_t position) const;
};

} // namespace us4
