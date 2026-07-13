# libFuzzer harnesses for the parsers that read bytes from model files
# potentially downloaded from anywhere (see #81.13). Opt-in via
# US4_BUILD_FUZZERS; combine with US4_ENABLE_ASAN/US4_ENABLE_UBSAN to catch
# memory-safety and UB bugs, not just crashes:
#
#   cmake -S . -B build-fuzz -G Ninja \
#     -DUS4_BUILD_FUZZERS=ON -DUS4_ENABLE_ASAN=ON -DUS4_ENABLE_UBSAN=ON \
#     -DCMAKE_CXX_COMPILER=clang++
#   cmake --build build-fuzz --target us4_fuzz_json_value
#   ./build-fuzz/runtime/fuzz/us4_fuzz_json_value \
#     -max_total_time=60 tests/fixtures/safetensors

set(US4_FUZZ_TARGETS
  us4_fuzz_json_value
  us4_fuzz_safetensors_reader
  us4_fuzz_gguf_reader
  us4_fuzz_bpe_tokenizer
)

foreach(target_name IN LISTS US4_FUZZ_TARGETS)
  string(REPLACE "us4_fuzz_" "" harness_name "${target_name}")
  add_executable(${target_name} fuzz_${harness_name}.cpp)
  target_link_libraries(${target_name} PRIVATE us4_runtime_core)
  target_include_directories(${target_name}
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}
      ${CMAKE_SOURCE_DIR}/runtime
      ${CMAKE_BINARY_DIR}/generated
  )
  target_compile_options(${target_name} PRIVATE -fsanitize=fuzzer)
  target_link_options(${target_name} PRIVATE -fsanitize=fuzzer)
endforeach()
