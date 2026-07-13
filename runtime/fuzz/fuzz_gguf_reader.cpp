#include <cstddef>
#include <cstdint>
#include <string>

#include "core/gguf_reader.h"
#include "fuzz/fuzz_temp_file.h"

// libFuzzer harness for GgufReader (issue #81.2b/#81.13) -- the GGUF binary
// container has more untrusted structure to walk than safetensors (a
// metadata key-value section with a generic per-type skip, including
// arrays, before the tensor info array is even reachable), so it gets its
// own harness rather than reusing the safetensors one.
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data,
                                      const std::size_t size) {
  const us4::fuzz::ScopedFuzzInputFile input(data, size, "-gguf.bin");

  std::string error;
  if (const auto reader = us4::GgufReader::Open(input.path(), &error);
      reader.has_value()) {
    for (const std::string &name :
         {std::string("embedding.weight"), std::string("lm_head.weight")}) {
      std::string readError;
      (void)reader->ReadFloat32(name, &readError);
    }
  }
  return 0;
}
