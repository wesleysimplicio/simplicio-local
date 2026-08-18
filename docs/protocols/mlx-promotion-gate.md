# MLX promotion gate

MLX-LM and native MLX are optional Apple Silicon providers. The Local first
checks the host architecture and module importability. Linux/Windows and
non-Apple hosts remain explicitly unavailable even if source files are present.

Promotion is staged:

1. fixture output parity produces `fixture-executed`;
2. published real-model parity with model, hardware and timing produces
   `real-model-executed`;
3. a reproducible benchmark with positive tokens, elapsed time and artifact
   metadata produces `benchmarked-on-target`.

A mismatch or incomplete metadata blocks promotion. No MLX flag or source
filename can make an unavailable native path appear operational.
