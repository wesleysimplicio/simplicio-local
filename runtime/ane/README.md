# ANE

Home for the optional ANE backend surface on Apple Silicon generations that can
advertise ANE/CoreML support. The current scaffold keeps compile/predict intent,
target chip expectations, and fallback discipline explicit without pretending to
execute real CoreML graphs on non-M5 hosts.

`LayerOffloader` is the policy layer above `AneBackend`: it keeps static dense
attention/MLP projections eligible for ANE while forcing embeddings, routers,
low-bit paths, and non-static shapes back to Metal or CPU.
