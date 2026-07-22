# libFuzzer/AFL++ harnesses for code that reads bytes from model files
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
#
# AFL++ uses the same LLVMFuzzerTestOneInput harnesses with a small file
# driver.  Select it explicitly and use afl-clang-fast++ as the compiler:
#
#   cmake -S . -B build-afl -DUS4_BUILD_FUZZERS=ON \
#     -DUS4_FUZZ_ENGINE=afl -DCMAKE_CXX_COMPILER=afl-clang-fast++
#   cmake --build build-afl --target us4_fuzz_dequant_int8
#   ./scripts/seed_quant_fuzz_corpus.py
#   afl-fuzz -i runtime/fuzz/corpus/dequant_int8 \
#     -o out/afl-dequant-int8 -- build-afl/runtime/fuzz/us4_fuzz_dequant_int8 @@

set(US4_FUZZ_ENGINE "libfuzzer" CACHE STRING
    "Fuzzing engine: libfuzzer or afl")
set_property(CACHE US4_FUZZ_ENGINE PROPERTY STRINGS libfuzzer afl)
if(NOT US4_FUZZ_ENGINE STREQUAL "libfuzzer" AND
   NOT US4_FUZZ_ENGINE STREQUAL "afl")
  message(FATAL_ERROR "US4_FUZZ_ENGINE must be libfuzzer or afl")
endif()

set(US4_FUZZ_TARGETS
  us4_fuzz_json_value
  us4_fuzz_safetensors_reader
  us4_fuzz_gguf_reader
  us4_fuzz_bpe_tokenizer
  us4_fuzz_dequant_int8
  us4_fuzz_dequant_int4
)

foreach(target_name IN LISTS US4_FUZZ_TARGETS)
  string(REPLACE "us4_fuzz_" "" harness_name "${target_name}")
  set(target_sources fuzz_${harness_name}.cpp)
  if(US4_FUZZ_ENGINE STREQUAL "afl")
    list(APPEND target_sources afl_driver.cpp)
  endif()
  add_executable(${target_name} ${target_sources})
  target_link_libraries(${target_name} PRIVATE us4_runtime_core)
  target_include_directories(${target_name}
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}
      ${CMAKE_SOURCE_DIR}/runtime
      ${CMAKE_BINARY_DIR}/generated
  )
  if(US4_FUZZ_ENGINE STREQUAL "libfuzzer")
    target_compile_options(${target_name} PRIVATE -fsanitize=fuzzer)
    target_link_options(${target_name} PRIVATE -fsanitize=fuzzer)
  endif()
endforeach()
