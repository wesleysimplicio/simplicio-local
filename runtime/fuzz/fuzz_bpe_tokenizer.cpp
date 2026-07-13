#include <cstddef>
#include <cstdint>
#include <string>

#include "core/bpe_tokenizer.h"
#include "fuzz/fuzz_temp_file.h"

// libFuzzer harness for BpeTokenizer::LoadFromFile -- a genuine
// tokenizer.json is untrusted JSON describing a potentially large
// vocab+merges table, downloaded alongside the model weights. This
// exercises both the load (JSON parse + vocab/merges extraction) and a
// subsequent Encode() call, since a tokenizer that loads but panics on
// arbitrary input text is just as much a bug as one that panics on load.
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data,
                                      const std::size_t size) {
  const us4::fuzz::ScopedFuzzInputFile input(data, size, "-tokenizer.json");

  std::string error;
  if (const auto tokenizer =
          us4::BpeTokenizer::LoadFromFile(input.path(), &error);
      tokenizer.has_value()) {
    (void)tokenizer->Encode("fuzz probe text");
    (void)tokenizer->EncodeIds("fuzz probe text");
  }
  return 0;
}
