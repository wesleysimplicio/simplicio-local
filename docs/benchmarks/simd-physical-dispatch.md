# SIMD physical dispatch evidence

This note records the implementation and the local evidence for the SIMD
epic (#304). A planner result is only promotable when the physical function
pointer, the scalar differential result, and the bounded latency gates all
agree.

## Merged implementation

| Issue | PR | Physical surface |
| --- | --- | --- |
| #305 | #314 | registry selects an invokable kernel function pointer |
| #306 | #315 | CPUID/HWCAP/sysctl and OS-state gated ISA snapshot |
| #307 | #316 | AVX2 Q8/Q4 packing and tails-safe kernels |
| #308 | #317 | AVX-512/VNNI candidate and shape/thermal/evidence gates |
| #309 | #318 | FP32/BF16/FP16 CPU matmul dispatch |
| #310 | #319 | RMSNorm, RoPE, softmax and activation physical paths |
| #311 | #320 | versioned packing, atomic artifacts, tiling and isolated batching |
| #312 | #321 | bounded tuning modes and physical-identity cache |
| #313 | #322 | differential, benchmark, safety and release gates/receipts |

The int8 AVX2 entry point now goes through the registry before invoking the
function pointer. `US4_DISABLE_SIMD=1` forces the portable scalar path without
recompilation. Advanced kernels remain optional and are never called unless
their ISA and measured gates pass.

## Reproducible local checks

```text
python3 -m unittest discover -s tests/local_data_plane -p 'test_*.py'
make -C engine/c test-c
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -Iruntime -c runtime/cpu/int8_matmul.cpp
g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -Iruntime -c runtime/benchmarks/simd_release_gate.cpp
```

The Python suite covers 192 tests at the time of this change. The C++ contract
tests are registered in the normal CMake/GTest suite; this execution image has
no CMake or GTest headers, so those targets cannot be built here.

## Evidence boundary

The repository contains tiny real-weight fixtures and a native
`real_forward_throughput` harness, but this image cannot build the complete
CMake runtime and has no ARM/AVX-512/AMX host. Therefore this PR records the
physical implementation and fail-closed gates; it does not claim a production
model speedup or close the epic without an installed-artifact run on the
applicable hardware. The release gate deliberately rejects missing
end-to-end model evidence.
