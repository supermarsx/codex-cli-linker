cmake_minimum_required(VERSION 3.15)

# Minimal CMake pipeline for the Python tool
project(codex_cli_linker_pipeline LANGUAGES NONE)

# Find a Python 3 interpreter
find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)

set(SRC_SCRIPT ${CMAKE_SOURCE_DIR}/codex-cli-linker.py)

# ---- Configurable run options (pass with -D...) ----
option(CODEX_AUTO       "Run with --auto"       OFF)
option(CODEX_FULL_AUTO  "Run with --full-auto"  OFF)
option(CODEX_JSON       "Also write JSON"       OFF)
option(CODEX_YAML       "Also write YAML"       OFF)
option(CODEX_DRY_RUN    "Use --dry-run"         OFF)
option(CODEX_VERBOSE    "Use --verbose"         OFF)

set(CODEX_BASE_URL   "" CACHE STRING "Base URL for --base-url (e.g. http://localhost:1234/v1)")
set(CODEX_PROVIDER   "" CACHE STRING "Provider id for --provider (e.g. lmstudio, ollama)")
set(CODEX_PROFILE    "" CACHE STRING "Profile name for --profile (e.g. lmstudio)")
set(CODEX_MODEL      "" CACHE STRING "Model id or substring for --model")
set(CODEX_MODEL_INDEX "" CACHE STRING "Model index for --model-index (integer as string)")

function(build_run_args out_var)
  set(args)
  if(CODEX_AUTO)
    list(APPEND args --auto)
  endif()
  if(CODEX_FULL_AUTO)
    list(APPEND args --full-auto)
  endif()
  if(CODEX_JSON)
    list(APPEND args --json)
  endif()
  if(CODEX_YAML)
    list(APPEND args --yaml)
  endif()
  if(CODEX_DRY_RUN)
    list(APPEND args --dry-run)
  endif()
  if(CODEX_VERBOSE)
    list(APPEND args --verbose)
  endif()
  if(NOT CODEX_BASE_URL STREQUAL "")
    list(APPEND args --base-url "${CODEX_BASE_URL}")
  endif()
  if(NOT CODEX_PROVIDER STREQUAL "")
    list(APPEND args --provider "${CODEX_PROVIDER}")
  endif()
  if(NOT CODEX_PROFILE STREQUAL "")
    list(APPEND args --profile "${CODEX_PROFILE}")
  endif()
  if(NOT CODEX_MODEL STREQUAL "")
    list(APPEND args --model "${CODEX_MODEL}")
  endif()
  if(NOT CODEX_MODEL_INDEX STREQUAL "")
    list(APPEND args --model-index "${CODEX_MODEL_INDEX}")
  endif()
  set(${out_var} "${args}" PARENT_SCOPE)
endfunction()

build_run_args(RUN_ARGS)

# ---- Targets ----

# Syntax sanity check (PEP 8 not enforced here; just byte-compile)
add_custom_target(check
  COMMAND ${Python3_EXECUTABLE} -m py_compile ${SRC_SCRIPT}
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Syntax check via py_compile"
  VERBATIM
)

# Run the tool with configured flags
add_custom_target(run
  COMMAND ${Python3_EXECUTABLE} ${SRC_SCRIPT} ${RUN_ARGS}
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Run codex-cli-linker.py with configured args"
  VERBATIM
)

# Hook Python unit tests into CTest
enable_testing()
add_test(NAME unit
  COMMAND ${Python3_EXECUTABLE} -m unittest -v
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

add_custom_target(test
  COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
  DEPENDS check
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  COMMENT "Run Python unit tests via CTest"
)

# Aggregate "ci" target
add_custom_target(ci DEPENDS check test)

