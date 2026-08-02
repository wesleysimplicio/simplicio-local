# Compatibility entry point for the vendored engine.
#
# The implementation-owned Makefile lives in engine/c. Keep this thin
# wrapper so the documented `make -C engine <target>` command works without
# duplicating the engine build graph or changing its working-directory
# assumptions.

ENGINE_DIR := $(CURDIR)/c

.PHONY: all glm test test-c test-python test-tokenizer test-chat-template \
        check portable sanitize fuzz-smoke fuzz-libfuzzer clean

all: glm

glm test test-c test-python test-tokenizer test-chat-template check portable \
sanitize fuzz-smoke fuzz-libfuzzer clean:
	$(MAKE) -C $(ENGINE_DIR) $@
