# Quantization fuzzing

The dequantization targets use an independent scalar oracle and cover odd
tails, group boundaries, zero inputs, and arbitrary packed nibbles:

- `us4_fuzz_dequant_int8`
- `us4_fuzz_dequant_int4`

Generate a reproducible corpus from the checked-in real-weight fixture:

```bash
python3 scripts/seed_quant_fuzz_corpus.py
```

For a production checkpoint, pass `--source path/to/model.safetensors`.
The generated `manifest.json` records the source SHA-256; generated binary
corpora are not committed.

## libFuzzer

```bash
cmake -S . -B build-fuzz -DUS4_BUILD_FUZZERS=ON \
  -DUS4_ENABLE_ASAN=ON -DUS4_ENABLE_UBSAN=ON \
  -DCMAKE_CXX_COMPILER=clang++
cmake --build build-fuzz --target us4_fuzz_dequant_int8 us4_fuzz_dequant_int4
build-fuzz/runtime/fuzz/us4_fuzz_dequant_int8 -max_total_time=300 \
  runtime/fuzz/corpus/dequant_int8
```

## AFL++

The same harnesses can be built with the AFL++ file driver:

```bash
cmake -S . -B build-afl -DUS4_BUILD_FUZZERS=ON \
  -DUS4_FUZZ_ENGINE=afl -DCMAKE_CXX_COMPILER=afl-clang-fast++
cmake --build build-afl --target us4_fuzz_dequant_int8
afl-fuzz -i runtime/fuzz/corpus/dequant_int8 \
  -o out/afl-dequant-int8 -- build-afl/runtime/fuzz/us4_fuzz_dequant_int8 @@
```

Crashes must be minimized and promoted to a regression test before fixing a
kernel. The corpus is derived from real fixture weights, not synthetic-only
inputs; the checked-in fixture is deliberately small enough for local runs.
