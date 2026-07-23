# MLX

Home for the primary MLX execution path on Apple Silicon.

Native execution contract:

- `native_mlx_backend.cpp` constructs real `mlx::core::array` values, calls
  `mlx::core::matmul`, forces execution with `mlx::core::eval`, and copies the
  evaluated result back for parity checks
- `mlx_bridge.{h,cpp}` reports availability only when native MLX was found and
  linked by CMake
- `dense_plan.{h,cpp}` materializes a 3-stage dense plan
  (`embedding -> attention -> projection`)
- the bridge can reference unified-shared allocations from
  `UnifiedAllocator`

Platform behavior:

- Apple builds discover the existing `mlx/mlx.h` and `libmlx`; no dependency is
  downloaded automatically
- non-Apple builds and Apple builds without MLX use the explicit native stub,
  reject evaluation, and expose the reason instead of simulating success
- shared buffer interop with Metal / unified memory
- execution wired into generation for dense and Llama-family adapters
- macOS/Apple Silicon parity, memory, and profiling evidence remains a real-host
  validation step
