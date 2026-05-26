add_executable(correctness_check
  correctness_check.cpp
)

target_link_libraries(correctness_check PRIVATE us4_runtime_core)

target_compile_definitions(correctness_check PRIVATE US4_SOURCE_DIR="${CMAKE_SOURCE_DIR}")

target_include_directories(correctness_check
  PRIVATE
    ${CMAKE_SOURCE_DIR}/runtime
    ${CMAKE_BINARY_DIR}/generated
)
