#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace us4 {

// Real .safetensors reader: parses the binary header (little-endian uint64
// header length + JSON tensor index) and reads actual tensor bytes from the
// file, instead of treating the extension as a hint and never opening the
// file. Only float32 tensors are exposed as data for now; other dtypes are
// reported through Dtype() so callers can decide how to handle them.
class SafetensorsReader {
public:
  struct TensorInfo {
    std::string dtype;
    std::vector<std::size_t> shape;
    std::size_t byteOffsetBegin = 0;
    std::size_t byteOffsetEnd = 0;
  };

  static std::optional<SafetensorsReader>
  Open(const std::filesystem::path &path, std::string *error = nullptr);

  bool HasTensor(const std::string &name) const {
    return tensors_.count(name) > 0;
  }

  const TensorInfo *Find(const std::string &name) const {
    const auto it = tensors_.find(name);
    return it == tensors_.end() ? nullptr : &it->second;
  }

  // Reads the raw float32 values for a tensor whose dtype is "F32". Returns
  // an empty vector and sets `error` for missing tensors, non-float dtypes,
  // or a truncated/corrupt file body.
  std::vector<float> ReadFloat32(const std::string &name,
                                 std::string *error = nullptr) const;

  std::size_t TensorCount() const { return tensors_.size(); }

private:
  std::filesystem::path path_;
  std::size_t dataSectionStart_ = 0;
  std::unordered_map<std::string, TensorInfo> tensors_;
};

} // namespace us4
