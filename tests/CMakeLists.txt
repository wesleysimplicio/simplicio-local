find_package(GTest CONFIG QUIET)

if(NOT GTest_FOUND)
  find_package(GTest QUIET)
endif()

# The runtime contract suite is the bulk of our coverage. When no system GTest
# is available (default GitHub macos/ubuntu runners, fresh dev boxes) fall back
# to a pinned FetchContent build so the contract tests always compile and run
# instead of being silently skipped.
if(NOT GTest_FOUND AND US4_FETCH_GTEST)
  include(FetchContent)
  FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.15.2
    GIT_SHALLOW TRUE
  )
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)
  if(TARGET gtest AND NOT TARGET GTest::gtest)
    add_library(GTest::gtest ALIAS gtest)
    add_library(GTest::gtest_main ALIAS gtest_main)
  endif()
  set(GTest_FOUND TRUE)
endif()

if(NOT GTest_FOUND)
  message(WARNING "GTest not found and US4_FETCH_GTEST is OFF. Building smoke tests only; contract tests will be skipped.")
endif()

add_subdirectory(unit)
