#pragma once

#include "adapters/dense_adapter_base.h"
#include "cache/multimodal_cache.h"

namespace us4 {

class MiniMaxMoEAdapter final : public DenseAdapterBase {
public:
  MiniMaxMoEAdapter();

  ArchitectureType Architecture() const override;
  bool SupportsMoe() const override;
  bool SupportsMlxBackend() const override;
  bool SupportsMetalBackend() const override;
  GenerationResult Generate(const GenerationRequest &request,
                            const RuntimeContext &context) const override;

protected:
  std::uint32_t Seed() const override;
  std::vector<std::string> Vocabulary() const override;
  std::string DefaultPromptToken() const override;

private:
  std::vector<float> BuildRouteLogits(const GenerationRequest &request,
                                      const ModelAsset *asset) const;
  std::string BuildRouteSignature(const RouterDecision &routing) const;
  std::vector<ModalityTokenState>
  BuildModalityState(const GenerationRequest &request) const;
};

} // namespace us4
