# CPU Scalar Reference Path

Sprint 02 introduces `runtime/cpu/` as the portable scalar reference path for dense execution.

- `scalar_matmul.*` is the safe GEMM baseline.
- `scalar_attention.*` is the safe attention baseline.
- `int8_matmul.*` owns portable INT8 GEMM dispatch. It selects NEON i8mm,
  NEON SDOT, or x86 AVX-512 VNNI only when the compiler and host make that
  path executable, and otherwise reports and runs the explicit scalar kernel.

The INT8 API keeps `ScalarInt8Matmul` public as the correctness oracle and
microbenchmark baseline. Accelerated kernels accumulate into signed 32-bit
lanes and write fp32 output, matching the existing runtime tensor contract.
