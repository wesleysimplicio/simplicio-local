#include "core/gguf_reader.h"

#include <array>
#include <fstream>
#include <limits>

namespace us4 {

namespace {

// GGUF metadata value types (distinct from the ggml tensor dtype enum).
enum class GgufValueType : std::uint32_t {
  kUint8 = 0,
  kInt8 = 1,
  kUint16 = 2,
  kInt16 = 3,
  kUint32 = 4,
  kInt32 = 5,
  kFloat32 = 6,
  kBool = 7,
  kString = 8,
  kArray = 9,
  kUint64 = 10,
  kInt64 = 11,
  kFloat64 = 12,
};

// Caps guard against a malformed/adversarial header causing an absurd
// allocation or an unbounded read loop -- the same defensive posture the
// safetensors JSON header parsing uses (see #81.5's DoS hardening).
constexpr std::uint64_t kMaxStringLength = 1ULL << 20;
constexpr std::uint64_t kMaxArrayCount = 1ULL << 20;
constexpr std::uint64_t kMaxDimensions = 1024;
constexpr std::uint64_t kMaxTensorOrKvCount = 1ULL << 20;

bool WriteError(std::string *error, const std::string &message) {
  if (error != nullptr) {
    *error = message;
  }
  return false;
}

template <typename T> bool ReadRaw(std::ifstream &file, T *out) {
  file.read(reinterpret_cast<char *>(out), sizeof(T));
  return static_cast<bool>(file);
}

bool ReadString(std::ifstream &file, std::string *out, std::string *error) {
  std::uint64_t length = 0;
  if (!ReadRaw(file, &length) || length > kMaxStringLength) {
    return WriteError(error, "gguf string length missing or exceeds bound");
  }
  out->resize(static_cast<std::size_t>(length));
  if (length > 0 &&
      !file.read(out->data(), static_cast<std::streamsize>(length))) {
    return WriteError(error, "gguf string body is truncated");
  }
  return true;
}

std::size_t ScalarValueSize(const GgufValueType type) {
  switch (type) {
  case GgufValueType::kUint8:
  case GgufValueType::kInt8:
  case GgufValueType::kBool:
    return 1;
  case GgufValueType::kUint16:
  case GgufValueType::kInt16:
    return 2;
  case GgufValueType::kUint32:
  case GgufValueType::kInt32:
  case GgufValueType::kFloat32:
    return 4;
  case GgufValueType::kUint64:
  case GgufValueType::kInt64:
  case GgufValueType::kFloat64:
    return 8;
  default:
    return 0;
  }
}

// Skips one metadata value of `type`, advancing the stream past it. Arrays
// are only supported one level deep (an array of arrays is rejected) --
// real GGUF metadata never nests arrays, and rejecting it caps the
// recursion an adversarial file could otherwise trigger.
bool SkipMetadataValue(std::ifstream &file, const GgufValueType type,
                       std::string *error) {
  if (type == GgufValueType::kString) {
    std::string discarded;
    return ReadString(file, &discarded, error);
  }
  if (type == GgufValueType::kArray) {
    std::uint32_t elementTypeRaw = 0;
    std::uint64_t count = 0;
    if (!ReadRaw(file, &elementTypeRaw) || !ReadRaw(file, &count) ||
        count > kMaxArrayCount) {
      return WriteError(error, "gguf array header missing or exceeds bound");
    }
    const auto elementType = static_cast<GgufValueType>(elementTypeRaw);
    if (elementType == GgufValueType::kArray) {
      return WriteError(error, "gguf nested arrays are not supported");
    }
    for (std::uint64_t index = 0; index < count; ++index) {
      if (!SkipMetadataValue(file, elementType, error)) {
        return false;
      }
    }
    return true;
  }
  const std::size_t scalarSize = ScalarValueSize(type);
  if (scalarSize == 0) {
    return WriteError(error, "gguf metadata value has an unknown type");
  }
  file.seekg(static_cast<std::streamoff>(scalarSize), std::ios::cur);
  return static_cast<bool>(file);
}

} // namespace

std::optional<GgufReader> GgufReader::Open(const std::filesystem::path &path,
                                           std::string *error) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    if (error != nullptr) {
      *error = "gguf file not found at " + path.string();
    }
    return std::nullopt;
  }

  std::array<char, 4> magic{};
  if (!file.read(magic.data(), magic.size()) ||
      std::string(magic.data(), magic.size()) != "GGUF") {
    if (error != nullptr) {
      *error = "gguf file has no valid 'GGUF' magic prefix "
               "(placeholder/non-binary file, not real tensor data)";
    }
    return std::nullopt;
  }

  std::uint32_t version = 0;
  std::uint64_t tensorCount = 0;
  std::uint64_t metadataCount = 0;
  if (!ReadRaw(file, &version) || !ReadRaw(file, &tensorCount) ||
      !ReadRaw(file, &metadataCount) || tensorCount > kMaxTensorOrKvCount ||
      metadataCount > kMaxTensorOrKvCount) {
    if (error != nullptr) {
      *error = "gguf header (version/tensor_count/metadata_kv_count) is "
               "missing or exceeds bound";
    }
    return std::nullopt;
  }

  std::uint32_t alignment = 32;
  for (std::uint64_t index = 0; index < metadataCount; ++index) {
    std::string key;
    if (!ReadString(file, &key, error)) {
      return std::nullopt;
    }
    std::uint32_t valueTypeRaw = 0;
    if (!ReadRaw(file, &valueTypeRaw)) {
      if (error != nullptr) {
        *error = "gguf metadata value type is missing";
      }
      return std::nullopt;
    }
    const auto valueType = static_cast<GgufValueType>(valueTypeRaw);
    if (key == "general.alignment" && valueType == GgufValueType::kUint32) {
      if (!ReadRaw(file, &alignment) || alignment == 0) {
        if (error != nullptr) {
          *error = "gguf general.alignment value is missing or invalid";
        }
        return std::nullopt;
      }
      continue;
    }
    if (!SkipMetadataValue(file, valueType, error)) {
      return std::nullopt;
    }
  }

  GgufReader reader;
  reader.path_ = path;

  for (std::uint64_t index = 0; index < tensorCount; ++index) {
    std::string name;
    if (!ReadString(file, &name, error)) {
      return std::nullopt;
    }
    std::uint32_t dimensionCount = 0;
    if (!ReadRaw(file, &dimensionCount) || dimensionCount > kMaxDimensions) {
      if (error != nullptr) {
        *error = "gguf tensor " + name +
                 " dimension count is missing or exceeds bound";
      }
      return std::nullopt;
    }
    std::vector<std::size_t> shape;
    shape.reserve(dimensionCount);
    for (std::uint32_t dim = 0; dim < dimensionCount; ++dim) {
      std::uint64_t dimValue = 0;
      if (!ReadRaw(file, &dimValue)) {
        if (error != nullptr) {
          *error = "gguf tensor " + name + " dimensions are truncated";
        }
        return std::nullopt;
      }
      shape.push_back(static_cast<std::size_t>(dimValue));
    }
    std::uint32_t ggmlType = 0;
    std::uint64_t offset = 0;
    if (!ReadRaw(file, &ggmlType) || !ReadRaw(file, &offset)) {
      if (error != nullptr) {
        *error = "gguf tensor " + name + " type/offset is truncated";
      }
      return std::nullopt;
    }
    TensorInfo info;
    info.ggmlType = ggmlType;
    info.shape = std::move(shape);
    info.byteOffset = static_cast<std::size_t>(offset);
    reader.tensors_.emplace(std::move(name), std::move(info));
  }

  if (reader.tensors_.empty()) {
    if (error != nullptr) {
      *error = "gguf file contains no real tensor entries";
    }
    return std::nullopt;
  }

  const std::size_t tensorInfoEnd = static_cast<std::size_t>(file.tellg());
  const std::size_t remainder = tensorInfoEnd % alignment;
  reader.dataSectionStart_ =
      remainder == 0 ? tensorInfoEnd : tensorInfoEnd + (alignment - remainder);

  return reader;
}

std::vector<float> GgufReader::ReadFloat32(const std::string &name,
                                           std::string *error) const {
  const TensorInfo *info = Find(name);
  if (info == nullptr) {
    if (error != nullptr) {
      *error = "tensor not found: " + name;
    }
    return {};
  }
  if (info->ggmlType != kGgmlTypeF32) {
    if (error != nullptr) {
      *error = "tensor " + name +
               " is not ggml F32 (type=" + std::to_string(info->ggmlType) + ")";
    }
    return {};
  }

  // A malformed/adversarial header can declare dimensions whose product
  // overflows size_t (wrapping to a small, wrong value) or that stays
  // within size_t but still exceeds std::vector<float>::max_size(),
  // which throws std::length_error -- an uncaught exception that would
  // abort the process instead of returning the usual explicit error.
  std::size_t elementCount = 1;
  for (const std::size_t dim : info->shape) {
    if (dim != 0 &&
        elementCount > std::numeric_limits<std::size_t>::max() / dim) {
      if (error != nullptr) {
        *error = "tensor " + name + " shape overflows size_t";
      }
      return {};
    }
    elementCount *= dim;
  }
  if (elementCount > std::numeric_limits<std::size_t>::max() / sizeof(float)) {
    if (error != nullptr) {
      *error = "tensor " + name + " byte length overflows size_t";
    }
    return {};
  }
  const std::size_t byteLength = elementCount * sizeof(float);

  std::error_code fileSizeError;
  const std::uintmax_t fileSize =
      std::filesystem::file_size(path_, fileSizeError);
  if (fileSizeError ||
      dataSectionStart_ + info->byteOffset + byteLength > fileSize) {
    if (error != nullptr) {
      *error = "tensor " + name + " data extends past the end of the file";
    }
    return {};
  }

  std::ifstream file(path_, std::ios::binary);
  if (!file) {
    if (error != nullptr) {
      *error = "unable to reopen gguf file " + path_.string();
    }
    return {};
  }
  file.seekg(static_cast<std::streamoff>(dataSectionStart_ + info->byteOffset));

  std::vector<float> values(elementCount);
  file.read(reinterpret_cast<char *>(values.data()),
            static_cast<std::streamsize>(byteLength));
  if (!file) {
    if (error != nullptr) {
      *error = "tensor " + name + " data is truncated in file body";
    }
    return {};
  }
  return values;
}

} // namespace us4
