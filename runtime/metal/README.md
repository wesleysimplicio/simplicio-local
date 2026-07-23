# Metal

Home for the Metal execution path.

Native execution contract:

- `native_metal_backend.mm` owns a real `MTLDevice`, `MTLCommandQueue`, compiled
  `MTLComputePipelineState`, shared `MTLBuffer` objects, and synchronous
  `MTLCommandBuffer` completion for fp32 GEMM
- `MetalCommandQueue::Matmul` records a dispatch only after the native command
  buffer completes successfully
- generic `Dispatch` calls without bound tensors are rejected and never counted
- `kernel_library.{h,cpp}` exposes a native metadata catalog for the Metal
  kernel set
- `kernels/{matmul,softmax,rmsnorm}.metal` already exist as versioned source
  files inside the repo
- `dense_dispatch.{h,cpp}` materializes the current dense dispatch sequence
  (`matmul -> softmax -> rmsnorm`)
- queue availability requires both an Apple Silicon probe and a live native
  Metal device/queue/pipeline
- shared allocations from `UnifiedAllocator` can be attached to dispatch
  records

Platform behavior:

- non-Apple builds compile `native_metal_backend_stub.cpp`; synthetic probe
  flags cannot enable Metal there
- softmax and rmsnorm still require typed buffer-binding wrappers before they
  can be executed by generation
- macOS parity and profiling evidence must be generated on real Apple Silicon;
  Linux tests only validate the fallback and interface contracts
