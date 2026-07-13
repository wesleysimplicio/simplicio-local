#include <cstddef>
#include <cstdint>
#include <exception>
#include <string>

#include "core/json_value.h"

// libFuzzer harness for JsonValue::Parse -- this is the parser that reads
// the JSON header embedded in every .safetensors file, so it processes
// bytes from model files that may come from anywhere. Parse() is documented
// to throw std::exception on malformed input; that's normal control flow
// here, not a crash to report, so it's caught and ignored. What this
// harness actually watches for is memory-safety bugs (ASan/UBSan) or an
// unbounded resource blowup (guarded by json_value.cpp's recursion depth
// cap, see #81.5) on adversarial input.
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *data,
                                      const std::size_t size) {
  const std::string input(reinterpret_cast<const char *>(data), size);
  try {
    (void)us4::JsonValue::Parse(input);
  } catch (const std::exception &) {
  }
  return 0;
}
