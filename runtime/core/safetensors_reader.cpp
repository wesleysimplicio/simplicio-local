#include "core/safetensors_reader.h"

#include <cstring>
#include <fstream>

#include "core/json_value.h"

namespace us4 {

std::optional<SafetensorsReader>
SafetensorsReader::Open(const std::filesystem::path &path, std::string *error) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    if (error != nullptr) {
      *error = "safetensors file not found at " + path.string();
    }
    return std::nullopt;
  }

  std::uint64_t headerLength = 0;
  file.read(reinterpret_cast<char *>(&headerLength), sizeof(headerLength));
  if (!file || headerLength == 0 || headerLength > (1ULL << 30)) {
    if (error != nullptr) {
      *error = "safetensors file has no valid 8-byte header length prefix "
               "(placeholder/non-binary file, not real tensor data)";
    }
    return std::nullopt;
  }

  std::string headerJson(headerLength, '\0');
  file.read(headerJson.data(), static_cast<std::streamsize>(headerLength));
  if (!file) {
    if (error != nullptr) {
      *error = "safetensors header is truncated";
    }
    return std::nullopt;
  }

  JsonValue header;
  try {
    header = JsonValue::Parse(headerJson);
  } catch (const std::exception &ex) {
    if (error != nullptr) {
      *error = std::string("failed to parse safetensors header: ") + ex.what();
    }
    return std::nullopt;
  }

  if (!header.IsObject()) {
    if (error != nullptr) {
      *error = "safetensors header is not a JSON object";
    }
    return std::nullopt;
  }

  SafetensorsReader reader;
  reader.path_ = path;
  reader.dataSectionStart_ = sizeof(headerLength) + headerLength;

  for (const auto &[name, entry] : header.Entries()) {
    if (name == "__metadata__" || !entry.IsObject()) {
      continue;
    }
    TensorInfo info;
    if (entry.Has("dtype") && entry["dtype"].IsString()) {
      info.dtype = entry["dtype"].AsString();
    }
    if (entry.Has("shape") && entry["shape"].IsArray()) {
      for (const JsonValue &dim : entry["shape"].AsArray()) {
        info.shape.push_back(static_cast<std::size_t>(dim.AsNumber()));
      }
    }
    if (entry.Has("data_offsets") && entry["data_offsets"].IsArray() &&
        entry["data_offsets"].AsArray().size() == 2) {
      info.byteOffsetBegin = static_cast<std::size_t>(
          entry["data_offsets"].AsArray()[0].AsNumber());
      info.byteOffsetEnd = static_cast<std::size_t>(
          entry["data_offsets"].AsArray()[1].AsNumber());
    }
    reader.tensors_.emplace(name, std::move(info));
  }

  if (reader.tensors_.empty()) {
    if (error != nullptr) {
      *error = "safetensors header contains no real tensor entries";
    }
    return std::nullopt;
  }

  return reader;
}

std::vector<float> SafetensorsReader::ReadFloat32(const std::string &name,
                                                  std::string *error) const {
  const TensorInfo *info = Find(name);
  if (info == nullptr) {
    if (error != nullptr) {
      *error = "tensor not found: " + name;
    }
    return {};
  }
  if (info->dtype != "F32") {
    if (error != nullptr) {
      *error = "tensor " + name + " is not F32 (dtype=" + info->dtype + ")";
    }
    return {};
  }

  const std::size_t byteLength = info->byteOffsetEnd - info->byteOffsetBegin;
  if (byteLength % sizeof(float) != 0) {
    if (error != nullptr) {
      *error = "tensor " + name + " byte length is not float32-aligned";
    }
    return {};
  }

  std::ifstream file(path_, std::ios::binary);
  if (!file) {
    if (error != nullptr) {
      *error = "unable to reopen safetensors file " + path_.string();
    }
    return {};
  }
  file.seekg(
      static_cast<std::streamoff>(dataSectionStart_ + info->byteOffsetBegin));

  std::vector<float> values(byteLength / sizeof(float));
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
