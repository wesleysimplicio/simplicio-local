#pragma once

#include "adapters/dense_adapter_base.h"
#include "adapters/llama/llama_config.h"

namespace us4 {

class LlamaAdapter final : public DenseAdapterBase {
public:
  LlamaAdapter();

  bool SupportsMlxBackend() const override;
  bool SupportsMetalBackend() const override;
  bool SupportsAneBackend() const override;
  GenerationResult Generate(const GenerationRequest &request,
                            const RuntimeContext &context) const override;

protected:
  std::uint32_t Seed() const override;
  std::vector<std::string> Vocabulary() const override;
  std::string DefaultPromptToken() const override;

private:
  // `asset`/`usedReal` follow the same contract as
  // DenseAdapterBase::BuildTokenEmbedding: when `asset` has a
  // shape-compatible real embedding tensor, these return the genuine row
  // instead of the deterministic synthetic placeholder, and set
  // `*usedReal` (when non-null) so Generate() can gate the value row's
  // synthetic positional perturbation and aggregate real-weight telemetry
  // precisely.
  std::vector<float> BuildQueryRow(std::size_t tokenId, std::uint32_t seed,
                                   std::size_t position,
                                   const LlamaConfig &config,
                                   const ModelAsset *asset = nullptr,
                                   bool *usedReal = nullptr) const;
  std::vector<float> BuildKeyRow(std::size_t tokenId, std::uint32_t seed,
                                 std::size_t position,
                                 const LlamaConfig &config,
                                 const ModelAsset *asset = nullptr,
                                 bool *usedReal = nullptr) const;
  std::vector<float> BuildValueRow(std::size_t tokenId, std::uint32_t seed,
                                   std::size_t position,
                                   const LlamaConfig &config,
                                   const ModelAsset *asset = nullptr,
                                   bool *usedReal = nullptr) const;
};

} // namespace us4
