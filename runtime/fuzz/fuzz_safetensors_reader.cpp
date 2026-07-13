#include <cstddef>
#include <cstdint>
#include <string>

#include "core/safetensors_reader.h"
#include "fuzz/fuzz_temp_file.h"

// libFuzzer harness for SafetensorsReader -- exercises both the binary
// header parse (Open) and the tensor byte read (ReadFloat32) on the same
// adversarial input, since a real .safetensors file downloaded from
// anywhere is exactly this: an untrusted 8-byte length prefix, untrusted
// JSON header, and untrusted raw tensor bytes (see #81.5's DoS/UB
// hardening this harness is meant to keep honest going forward).
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data,
                                      const std::size_t size) {
  const us4::fuzz::ScopedFuzzInputFile input(data, size, "-safetensors.bin");

  std::string error;
  if (const auto reader = us4::SafetensorsReader::Open(input.path(), &error);
      reader.has_value()) {
    for (const std::string &name :
         {std::string("embedding.weight"), std::string("lm_head.weight")}) {
      std::string readError;
      (void)reader->ReadFloat32(name, &readError);
    }
  }
  return 0;
}
