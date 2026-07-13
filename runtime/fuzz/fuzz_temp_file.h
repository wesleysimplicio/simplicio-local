#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>

#include <unistd.h>

namespace us4::fuzz {

// The parsers under test (SafetensorsReader::Open, GgufReader::Open,
// BpeTokenizer::LoadFromFile) all take a filesystem path rather than an
// in-memory buffer, since they read real model files. This writes each
// fuzz input to a scratch file so those APIs can be exercised directly,
// and removes it on scope exit. The path is unique per process (pid) so
// concurrent libFuzzer worker processes (`-jobs=N`) don't collide.
class ScopedFuzzInputFile {
public:
  ScopedFuzzInputFile(const std::uint8_t *data, const std::size_t size,
                      const std::string &suffix)
      : path_(std::filesystem::temp_directory_path() /
              ("us4-fuzz-" + std::to_string(::getpid()) + suffix)) {
    std::ofstream file(path_, std::ios::binary | std::ios::trunc);
    file.write(reinterpret_cast<const char *>(data),
               static_cast<std::streamsize>(size));
  }

  ~ScopedFuzzInputFile() {
    std::error_code ignored;
    std::filesystem::remove(path_, ignored);
  }

  ScopedFuzzInputFile(const ScopedFuzzInputFile &) = delete;
  ScopedFuzzInputFile &operator=(const ScopedFuzzInputFile &) = delete;

  const std::filesystem::path &path() const { return path_; }

private:
  std::filesystem::path path_;
};

} // namespace us4::fuzz
