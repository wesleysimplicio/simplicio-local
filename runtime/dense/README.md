# Dense layer streaming

`DenseLayerStreamExecutor` is the explicit `demo-dense` slow path for dense
models whose complete weights cannot be resident at once.

- Weights are row-major float32 matrices in one or more file ranges described
  by `DenseLayerDescriptor`.
- The reader loads bounded row slices. It never materializes a complete layer
  unless the configured slice is itself that large.
- Execution owns one active weight slice and at most one asynchronous
  prefetch slot, including across layer boundaries: the first slice of layer
  N+1 is read while the final slice of N computes.
  `peakBufferedWeightBytesUpperBound` therefore reports the conservative
  active-plus-prefetch bound, not measured RSS.
- Activations advance only after a whole layer completes. Cancellation or any
  read error returns an empty output, so callers cannot mistake a partial
  activation for a generated result.
- Timing metrics are raw wall-clock durations. They are useful for receipts,
  but the tiny demo is not a throughput claim and does not establish that a
  70B checkpoint works on a 16 GB machine.

Run the generated tiny demonstration after building:

```bash
./build/runtime/benchmarks/dense_stream_demo
```

The demo creates a temporary 3-layer fixture, runs it with two rows per slice,
prints the bounded-memory and timing receipt, checks the known output, and
deletes the fixture. It downloads no model weights.
