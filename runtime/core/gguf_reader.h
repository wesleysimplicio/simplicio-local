#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// Real .gguf reader: parses the binary GGUF container (magic + version +
// tensor/metadata counts, metadata key-value section, tensor info array,
// aligned tensor data section) and reads actual tensor bytes from the file,
// instead of treating the extension as a hint and never opening the file.
// Only the F32 ggml tensor type is exposed as readable data for now; other
// types are reported through GgmlType() so callers can decide how to
// handle them (e.g. fall back to synthetic weights).
class GgufReader {
public:
  // ggml_type values this reader recognizes. Anything else is stored as-is
  // in TensorInfo::ggmlType but ReadFloat32() rejects it.
  static constexpr std::uint32_t kGgmlTypeF32 = 0;

  struct TensorInfo {
    std::uint32_t ggmlType = 0;
    std::vector<std::size_t> shape;
    std::size_t byteOffset = 0; // relative to the tensor data section start
  };

  static std::optional<GgufReader> Open(const std::filesystem::path &path,
                                        std::string *error = nullptr);

  bool HasTensor(const std::string &name) const {
    return tensors_.count(name) > 0;
  }

  const TensorInfo *Find(const std::string &name) const {
    const auto it = tensors_.find(name);
    return it == tensors_.end() ? nullptr : &it->second;
  }

  // Reads the raw float32 values for a tensor whose ggml_type is F32.
  // Returns an empty vector and sets `error` for missing tensors,
  // non-float32 types, or a truncated/corrupt file body.
  std::vector<float> ReadFloat32(const std::string &name,
                                 std::string *error = nullptr) const;

  std::size_t TensorCount() const { return tensors_.size(); }

private:
  std::filesystem::path path_;
  std::size_t dataSectionStart_ = 0;
  std::unordered_map<std::string, TensorInfo> tensors_;
};

} // namespace us4
