# engine/ — vendored colibri C inference engine (ADR-010).
#
# This is a *separate* build from the native C++ runtime in runtime/.
# The colibri Makefile (engine/c/Makefile) is the real, tested build tool
# for this engine and is intentionally NOT reimplemented in CMake — these
# targets just delegate to it via add_custom_target, so `cmake --build`
# users get a convenient entry point without duplicating build logic.
#
# None of these targets are part of the default `all` build of the
# us4-cli/runtime tree: they are opt-in, invoked explicitly by name.

find_program(US4_ENGINE_MAKE make)

if(US4_ENGINE_MAKE)
  add_custom_target(engine-colibri
    COMMAND ${US4_ENGINE_MAKE} glm
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/c
    COMMENT "Building vendored colibri engine (engine/c/Makefile -> glm)"
    VERBATIM
  )

  add_custom_target(engine-colibri-test
    COMMAND ${US4_ENGINE_MAKE} test
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/c
    COMMENT "Running vendored colibri engine test suite (engine/c/Makefile -> test)"
    VERBATIM
  )

  add_custom_target(engine-colibri-clean
    COMMAND ${US4_ENGINE_MAKE} clean
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/c
    COMMENT "Cleaning vendored colibri engine build artifacts"
    VERBATIM
  )
else()
  message(STATUS "engine/: 'make' not found, skipping engine-colibri targets (see engine/README.md to build manually)")
endif()
