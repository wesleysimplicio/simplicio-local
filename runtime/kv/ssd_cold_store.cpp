#include "kv/ssd_cold_store.h"

#include <cctype>
#include <fstream>

namespace us4 {

namespace {

std::string SanitizeKey(const std::string &key) {
  std::string sanitized;
  sanitized.reserve(key.size());
  for (const char ch : key) {
    const unsigned char byte = static_cast<unsigned char>(ch);
    if (std::isalnum(byte) != 0 || ch == '-' || ch == '_' || ch == '.') {
      sanitized.push_back(ch);
    } else {
      sanitized.push_back('_');
    }
  }
  return sanitized.empty() ? "kv_page" : sanitized;
}

} // namespace

SsdColdStore::SsdColdStore(std::filesystem::path root)
    : root_(std::move(root)) {
  std::filesystem::create_directories(root_);
}

bool SsdColdStore::Flush(const std::string &key,
                         const std::vector<float> &values) {
  std::ofstream stream(root_ / (SanitizeKey(key) + ".bin"), std::ios::binary);
  if (!stream.is_open()) {
    return false;
  }
  const std::size_t count = values.size();
  stream.write(reinterpret_cast<const char *>(&count), sizeof(count));
  stream.write(reinterpret_cast<const char *>(values.data()),
               static_cast<std::streamsize>(sizeof(float) * values.size()));
  return stream.good();
}

std::optional<std::vector<float>>
SsdColdStore::Restore(const std::string &key) const {
  std::ifstream stream(root_ / (SanitizeKey(key) + ".bin"), std::ios::binary);
  if (!stream.is_open()) {
    return std::nullopt;
  }
  std::size_t count = 0;
  stream.read(reinterpret_cast<char *>(&count), sizeof(count));
  std::vector<float> values(count, 0.0F);
  stream.read(reinterpret_cast<char *>(values.data()),
              static_cast<std::streamsize>(sizeof(float) * values.size()));
  if (!stream.good() && !stream.eof()) {
    return std::nullopt;
  }
  return values;
}

} // namespace us4
