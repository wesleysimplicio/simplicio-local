# OpenAI-compatible adapter

The optional HTTP adapter is a thin translation layer over the already-running
Local daemon. It does not create a second model handle, backend process or
lifecycle. Requests become the same internal `generate` operation and terminal
receipts are returned as metadata.

The default bind is loopback. A non-loopback bind requires a bearer token.
Request bodies are bounded to 1 MiB, CORS is disabled by default, unsupported
sampling fields are rejected, and `tools`/function calling can only be treated
as forbidden candidates: no tool is executed by Local. SSE streaming is
backpressured by the HTTP write boundary. Embeddings remain disabled until a
separate backend capability is proven.
