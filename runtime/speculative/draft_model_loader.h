#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace us4 {

// DraftModelLoader contract.
//
// A draft model is a small companion model used for speculative decoding. The
// loader needs to keep the tokenizer assumption explicit so the verifier can
// trust that draft tokens map cleanly into the target model's vocabulary.

struct DraftModelDescriptor {
  std::string family;
  std::string modelId;
  std::string tokenizerHash;
  std::string filePath;
  std::string weightFormat;
  std::string targetFamily;
  std::string targetModelId;
  std::string architecture;
  std::size_t vocabularySize = 0;
  std::string backend;
  std::string device;
};

// Parse a draft-model manifest body. The contract is intentionally simple so
// tests can exercise the schema without touching disk.
std::optional<DraftModelDescriptor>
ParseDraftModelManifestBody(const std::string &manifestBody);

struct DraftModelCompatibilityRequest {
  std::string targetFamily;
  std::string targetModelId;
  std::string targetTokenizerHash;
  std::string targetArchitecture;
  std::size_t targetVocabularySize = 0;
  std::string targetBackend;
  std::string targetDevice;
  bool targetUsesSharedTokenizer = true;
  bool allowSeparateDevice = true;
};

struct DraftModelCompatibilityResult {
  bool compatible = false;
  std::vector<std::string> reasons;
  std::string targetDevice;
  std::string draftDevice;
};

// Validate the pair before either model is loaded. An absent comparison value
// is treated as unknown, never as proof of compatibility.
DraftModelCompatibilityResult ValidateDraftModelCompatibility(
    const DraftModelDescriptor &draft,
    const DraftModelCompatibilityRequest &request);

}  // namespace us4
