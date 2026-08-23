#include "speculative/draft_model_loader.h"

#include <cctype>
#include <charconv>
#include <sstream>
#include <string_view>

namespace us4 {

namespace {

std::string Trim(std::string_view value) {
  std::size_t begin = 0;
  std::size_t end = value.size();
  while (begin < end && std::isspace(static_cast<unsigned char>(value[begin]))) {
    ++begin;
  }
  while (end > begin &&
         std::isspace(static_cast<unsigned char>(value[end - 1]))) {
    --end;
  }
  return std::string(value.substr(begin, end - begin));
}

bool ParseSize(const std::string &value, std::size_t *out) {
  if (out == nullptr || value.empty()) {
    return false;
  }
  const auto *begin = value.data();
  const auto *end = begin + value.size();
  const auto parsed = std::from_chars(begin, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end;
}

} // namespace

std::optional<DraftModelDescriptor>
ParseDraftModelManifestBody(const std::string &manifestBody) {
  DraftModelDescriptor descriptor;
  std::istringstream stream(manifestBody);
  std::string line;
  while (std::getline(stream, line)) {
    const auto trimmed = Trim(line);
    if (trimmed.empty() || trimmed.front() == '#') {
      continue;
    }
    const auto eq = trimmed.find('=');
    if (eq == std::string::npos) {
      continue;
    }
    const std::string key = Trim(trimmed.substr(0, eq));
    const std::string value = Trim(trimmed.substr(eq + 1));
    if (key == "family") {
      descriptor.family = value;
    } else if (key == "model_id") {
      descriptor.modelId = value;
    } else if (key == "tokenizer_hash") {
      descriptor.tokenizerHash = value;
    } else if (key == "file") {
      descriptor.filePath = value;
    } else if (key == "weight_format") {
      descriptor.weightFormat = value;
    } else if (key == "target_family") {
      descriptor.targetFamily = value;
    } else if (key == "target_model_id") {
      descriptor.targetModelId = value;
    } else if (key == "architecture") {
      descriptor.architecture = value;
    } else if (key == "vocab_size") {
      if (!ParseSize(value, &descriptor.vocabularySize)) {
        return std::nullopt;
      }
    } else if (key == "backend") {
      descriptor.backend = value;
    } else if (key == "device") {
      descriptor.device = value;
    }
  }
  if (descriptor.family.empty() || descriptor.modelId.empty() ||
      descriptor.tokenizerHash.empty() || descriptor.filePath.empty() ||
      descriptor.weightFormat.empty()) {
    return std::nullopt;
  }
  return descriptor;
}

DraftModelCompatibilityResult ValidateDraftModelCompatibility(
    const DraftModelDescriptor &draft,
    const DraftModelCompatibilityRequest &request) {
  DraftModelCompatibilityResult result;
  result.targetDevice = request.targetDevice;
  result.draftDevice = draft.device;

  if (!request.targetUsesSharedTokenizer) {
    result.reasons.push_back("target-does-not-use-shared-tokenizer");
  }
  if (!request.targetTokenizerHash.empty() &&
      request.targetTokenizerHash != draft.tokenizerHash) {
    result.reasons.push_back("tokenizer-hash-mismatch");
  }
  if (!request.targetFamily.empty() && !draft.family.empty() &&
      request.targetFamily != draft.family) {
    result.reasons.push_back("model-family-mismatch");
  }
  if (!draft.targetFamily.empty() && !request.targetFamily.empty() &&
      draft.targetFamily != request.targetFamily) {
    result.reasons.push_back("draft-target-family-mismatch");
  }
  if (request.targetVocabularySize != 0 && draft.vocabularySize != 0 &&
      request.targetVocabularySize != draft.vocabularySize) {
    result.reasons.push_back("vocabulary-size-mismatch");
  }
  if (!request.targetArchitecture.empty() && !draft.architecture.empty() &&
      request.targetArchitecture != draft.architecture) {
    result.reasons.push_back("architecture-mismatch");
  }
  if (!request.targetBackend.empty() && !draft.backend.empty() &&
      request.targetBackend != draft.backend) {
    result.reasons.push_back("backend-mismatch");
  }
  if (!request.targetDevice.empty() && !draft.device.empty() &&
      request.targetDevice != draft.device && !request.allowSeparateDevice) {
    result.reasons.push_back("separate-device-not-allowed");
  }
  result.compatible = result.reasons.empty();
  return result;
}

} // namespace us4
