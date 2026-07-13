#include "adapters/llama/llama_adapter.h"
#include "adapters/llama/llama_config.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <functional>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "core/backend_selector.h"
#include "core/gqa_attention.h"
#include "core/rope.h"
#include "core/tensor.h"
#include "neon/neon_matmul.h"

namespace us4 {

namespace {

std::vector<float> ReadTensorRow(const Tensor &tensor) {
  const float *source = tensor.DataAsFloat32();
  return {source, source + tensor.ElementCount()};
}

void DecorateLlamaResult(GenerationResult &result) {
  result.family = "llama";
  if (!result.generatedTokens.empty()) {
    result.generatedTokens[0] = "llama";
  }
  if (!result.text.empty()) {
    result.text = "llama " + result.text;
  }
}

} // namespace

LlamaAdapter::LlamaAdapter() : DenseAdapterBase("llama", "llama-3.1-8b") {}

bool LlamaAdapter::SupportsMlxBackend() const { return true; }

bool LlamaAdapter::SupportsMetalBackend() const { return true; }

bool LlamaAdapter::SupportsAneBackend() const { return true; }

std::vector<float> LlamaAdapter::BuildQueryRow(const std::size_t tokenId,
                                               const std::uint32_t seed,
                                               const std::size_t position,
                                               const LlamaConfig &config,
                                               const ModelAsset *asset,
                                               bool *usedReal) const {
  Tensor row({1, config.hiddenSize}, DType::kFloat32);
  CopyVectorToTensorValues(
      BuildTokenEmbedding(tokenId, config.hiddenSize, seed, asset, usedReal),
      row);
  ApplyRopeInPlace(row, position, config.ropeTheta, config.ropeScaling,
                   config.ropeScale);
  return ReadTensorRow(row);
}

std::vector<float>
LlamaAdapter::BuildKeyRow(const std::size_t tokenId, const std::uint32_t seed,
                          const std::size_t position, const LlamaConfig &config,
                          const ModelAsset *asset, bool *usedReal) const {
  const std::size_t kvWidth = config.kvHeads * config.headDim;
  Tensor row({1, kvWidth}, DType::kFloat32);
  CopyVectorToTensorValues(
      BuildTokenEmbedding(tokenId, kvWidth, seed + 11U, asset, usedReal), row);
  ApplyRopeInPlace(row, position, config.ropeTheta, config.ropeScaling,
                   config.ropeScale);
  return ReadTensorRow(row);
}

std::vector<float> LlamaAdapter::BuildValueRow(const std::size_t tokenId,
                                               const std::uint32_t seed,
                                               const std::size_t position,
                                               const LlamaConfig &config,
                                               const ModelAsset *asset,
                                               bool *usedReal) const {
  const std::size_t kvWidth = config.kvHeads * config.headDim;
  bool embeddingIsReal = false;
  std::vector<float> row = BuildTokenEmbedding(tokenId, kvWidth, seed + 29U,
                                               asset, &embeddingIsReal);
  if (!embeddingIsReal) {
    for (std::size_t hidden = 0; hidden < row.size(); ++hidden) {
      row[hidden] += static_cast<float>((position + hidden) % 5U) * 0.01F;
    }
  }
  if (usedReal != nullptr) {
    *usedReal = embeddingIsReal;
  }
  return row;
}

GenerationResult LlamaAdapter::Generate(const GenerationRequest &request,
                                        const RuntimeContext &context) const {
  const BackendSelection backendSelection = SelectBackend(
      context.hardware(), context.mode(), *this, request.requestedBackend);
  if (backendSelection.selected != BackendType::kNeon) {
    GenerationResult result = DenseAdapterBase::Generate(request, context);
    DecorateLlamaResult(result);
    return result;
  }

  RuntimeContext &mutableContext = const_cast<RuntimeContext &>(context);
  mutableContext.SetBackend(backendSelection.selected);

  const std::vector<std::string> vocabulary =
      (request.asset != nullptr && !request.asset->vocabulary.empty())
          ? request.asset->vocabulary
          : Vocabulary();
  const std::uint32_t activeSeed =
      (request.asset != nullptr && request.asset->seed != 0U)
          ? request.asset->seed
          : Seed();
  const LlamaConfig config = ResolveLlamaConfig(request.asset);
  const std::size_t kvWidth = config.kvHeads * config.headDim;

  bool usedRealBpeTokenizer = false;
  std::string tokenizerFallbackReason;
  std::vector<std::string> promptTokens =
      TokenizePrompt(request, &usedRealBpeTokenizer, &tokenizerFallbackReason);
  if (promptTokens.empty()) {
    if (request.asset != nullptr &&
        !request.asset->defaultPromptToken.empty()) {
      promptTokens.push_back(request.asset->defaultPromptToken);
    } else {
      promptTokens.push_back(DefaultPromptToken());
    }
  }

  std::vector<std::size_t> tokenIds;
  tokenIds.reserve(promptTokens.size() + request.maxTokens);
  for (const std::string &token : promptTokens) {
    tokenIds.push_back(TokenIdFor(token, vocabulary));
  }

  // Tracks whether ANY BuildQueryRow/BuildKeyRow/BuildValueRow/
  // BuildOutputProjection call in this Generate() actually used real
  // weights (for telemetry only), the same aggregate-vs-per-call
  // distinction DenseAdapterBase::Generate makes -- per-call synthetic
  // perturbation suppression always uses that specific call's own
  // `usedReal` result.
  bool anyRealWeightUsed = false;

  const std::string prefixKey =
      BuildPromptCacheKeyForFamily(activeSeed, promptTokens);
  mutableContext.prefixCache().Retain(prefixKey);

  std::vector<float> keyBuffer;
  std::vector<float> valueBuffer;
  bool kvCacheHit = false;
  bool kvRestoredFromColdStore = false;
  std::size_t kvSummaryRows = 0U;
  if (const std::optional<KvPage> cachedPage =
          mutableContext.kvPager().Lookup(prefixKey);
      cachedPage.has_value() && cachedPage->rowWidth == kvWidth &&
      cachedPage->rowCount == promptTokens.size() &&
      cachedPage->keys.size() == cachedPage->values.size()) {
    keyBuffer = cachedPage->keys;
    valueBuffer = cachedPage->values;
    kvCacheHit = true;
  } else {
    if (TryRestorePromptKvFromColdStore(mutableContext, prefixKey, kvWidth,
                                        tokenIds.size(), keyBuffer,
                                        valueBuffer)) {
      kvCacheHit = true;
      kvRestoredFromColdStore = true;
    } else {
      keyBuffer.reserve(tokenIds.size() * kvWidth);
      valueBuffer.reserve(tokenIds.size() * kvWidth);
      for (std::size_t index = 0; index < tokenIds.size(); ++index) {
        bool keyIsReal = false;
        bool valueIsReal = false;
        const std::vector<float> keyRow =
            BuildKeyRow(tokenIds[index], activeSeed, index, config,
                        request.asset, &keyIsReal);
        const std::vector<float> valueRow =
            BuildValueRow(tokenIds[index], activeSeed, index, config,
                          request.asset, &valueIsReal);
        anyRealWeightUsed = anyRealWeightUsed || keyIsReal || valueIsReal;
        keyBuffer.insert(keyBuffer.end(), keyRow.begin(), keyRow.end());
        valueBuffer.insert(valueBuffer.end(), valueRow.begin(), valueRow.end());
      }
    }
    kvSummaryRows = MaybeCompactPromptKv(mutableContext, prefixKey, keyBuffer,
                                         valueBuffer, kvWidth);
    mutableContext.kvPager().Append(prefixKey, keyBuffer, valueBuffer, kvWidth);
  }

  std::vector<std::string> generatedTokens;
  generatedTokens.reserve(request.maxTokens);
  for (std::size_t step = 0; step < request.maxTokens; ++step) {
    const std::size_t sequenceLength = keyBuffer.size() / kvWidth;
    Tensor key({sequenceLength, kvWidth}, DType::kFloat32);
    Tensor value({sequenceLength, kvWidth}, DType::kFloat32);
    Tensor query({1, config.hiddenSize}, DType::kFloat32);
    Tensor contextTensor({1, config.hiddenSize}, DType::kFloat32);
    Tensor logits({1, vocabulary.size()}, DType::kFloat32);

    CopyVectorToTensorValues(keyBuffer, key);
    CopyVectorToTensorValues(valueBuffer, value);

    bool queryIsReal = false;
    CopyVectorToTensorValues(BuildQueryRow(tokenIds.back(), activeSeed,
                                           sequenceLength - 1U, config,
                                           request.asset, &queryIsReal),
                             query);
    anyRealWeightUsed = anyRealWeightUsed || queryIsReal;

    std::string error;
    if (!GqaAttention(query, key, value, config.queryHeads, config.kvHeads,
                      contextTensor, &error)) {
      generatedTokens.push_back("gqa-error");
      break;
    }

    const ModelAsset *projectionAsset =
        backendSelection.selected == BackendType::kNeon ? request.asset
                                                        : nullptr;
    bool projectionIsReal = false;
    Tensor projection({config.hiddenSize, vocabulary.size()}, DType::kFloat32);
    if (!MaterializeProjectionForAsset(
            BuildOutputProjection(vocabulary, config.hiddenSize, activeSeed,
                                  request.asset, &projectionIsReal),
            {config.hiddenSize, vocabulary.size()}, projectionAsset, projection,
            &error, projectionIsReal)) {
      generatedTokens.push_back("projection-error");
      break;
    }
    anyRealWeightUsed = anyRealWeightUsed || projectionIsReal;
    const bool matmulOk = NeonMatmul(contextTensor, projection, logits, &error);
    if (!matmulOk) {
      generatedTokens.push_back("matmul-error");
      break;
    }

    const float *logitData = logits.DataAsFloat32();
    std::size_t bestIndex = 0U;
    float bestValue = logitData[0];
    for (std::size_t index = 1; index < vocabulary.size(); ++index) {
      const float bias =
          static_cast<float>(((step + 1U) * (index + 5U)) % 9U) * 0.003F;
      const float candidate = logitData[index] + bias;
      if (candidate > bestValue) {
        bestValue = candidate;
        bestIndex = index;
      }
    }

    generatedTokens.push_back(vocabulary[bestIndex]);
    tokenIds.push_back(bestIndex);

    bool nextKeyIsReal = false;
    bool nextValueIsReal = false;
    const std::vector<float> nextKeyRow =
        BuildKeyRow(bestIndex, activeSeed, sequenceLength, config,
                    request.asset, &nextKeyIsReal);
    const std::vector<float> nextValueRow =
        BuildValueRow(bestIndex, activeSeed, sequenceLength, config,
                      request.asset, &nextValueIsReal);
    anyRealWeightUsed = anyRealWeightUsed || nextKeyIsReal || nextValueIsReal;
    keyBuffer.insert(keyBuffer.end(), nextKeyRow.begin(), nextKeyRow.end());
    valueBuffer.insert(valueBuffer.end(), nextValueRow.begin(),
                       nextValueRow.end());
  }

  GenerationResult result = FinalizeGenerationResult(
      request, context, backendSelection, std::move(promptTokens),
      std::move(generatedTokens), kvCacheHit, kvRestoredFromColdStore,
      kvSummaryRows, config.hiddenSize, usedRealBpeTokenizer,
      tokenizerFallbackReason, anyRealWeightUsed);
  DecorateLlamaResult(result);
  return result;
}

std::uint32_t LlamaAdapter::Seed() const { return 31800U; }

std::vector<std::string> LlamaAdapter::Vocabulary() const {
  return {"llama", "apple",  "runtime", "dense",  "adapter", "gqa",
          "rope",  "metal",  "local",   "tokens", "reply",   "hello",
          ".",     "steady", "wide",    "context"};
}

std::string LlamaAdapter::DefaultPromptToken() const { return "hello"; }

} // namespace us4
