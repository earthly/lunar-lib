# C/C++ Project Guardrails

Enforces C/C++ project structure, build standards, and code quality.

## Overview

This policy validates C/C++ projects against best practices for build system configuration, language standard compliance, static analysis, and CI/CD toolchain versions. It ensures projects have a proper build system, use modern C++ standards, pass cppcheck analysis, and maintain up-to-date compilers in CI.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `build-system-exists` | Validates a build system is present | No CMake, Make, Meson, or other build system found |
| `min-cpp-standard` | Ensures minimum C++ standard | C++ standard too old (e.g., C++11 when C++17 required) |
| `cppcheck-clean` | Ensures cppcheck warnings within threshold | Too many cppcheck warnings |
| `min-compiler-version-cicd` | Ensures minimum compiler version in CI | CI gcc/clang version too old |
| `min-cmake-version-cicd` | Ensures minimum CMake version in CI | CI CMake version too old |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.cpp` | object | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |
| `.lang.cpp.build_systems` | array | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |
| `.lang.cpp.cpp_standard` | string | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |
| `.lang.cpp.lint.warnings` | array | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |
| `.lang.cpp.native.cppcheck` | object | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |
| `.lang.cpp.cicd.cmds` | array | [`cpp`](https://github.com/earthly/lunar-lib/tree/main/collectors/cpp) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/cpp@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # include: [build-system-exists, min-cpp-standard]  # Only run specific checks
    with:
      min_cpp_standard: "17"           # Minimum C++ standard (default: "17")
      max_cppcheck_warnings: "0"       # Maximum cppcheck warnings (default: "0")
      min_compiler_version: "12.0.0"   # Minimum gcc/clang version in CI (default: "12.0.0")
      min_cmake_version: "3.20.0"      # Minimum CMake version in CI (default: "3.20.0")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "cpp": {
      "build_systems": ["cmake"],
      "cmake_exists": true,
      "cpp_standard": "20",
      "lint": {
        "warnings": []
      },
      "native": {
        "cppcheck": {
          "passed": true,
          "error_count": 0,
          "warning_count": 0
        }
      },
      "cicd": {
        "cmds": [
          { "cmd": "g++ -std=c++20 -O2 main.cpp", "version": "13.2.0" },
          { "cmd": "cmake --build .", "version": "3.28.0" }
        ]
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "cpp": {
      "build_systems": [],
      "cpp_standard": "11",
      "lint": {
        "warnings": [
          { "file": "src/main.cpp", "line": 42, "severity": "warning", "message": "Variable 'x' is not initialized", "id": "uninitvar" }
        ]
      },
      "cicd": {
        "cmds": [
          { "cmd": "g++ main.cpp", "version": "9.4.0" },
          { "cmd": "cmake --build .", "version": "3.16.0" }
        ]
      }
    }
  }
}
```

**Failure messages:**
- `"No build system detected. C/C++ projects need CMake, Make, Meson, or another build system."`
- `"C++ standard 11 is below minimum 17. Update CMAKE_CXX_STANDARD or compiler flags to use C++17 or later."`
- `"1 cppcheck warning(s) found, maximum allowed is 0. Run 'cppcheck' and fix all warnings."`
- `"Compiler version 9.4.0 is below minimum 12.0.0. Update gcc/clang in your CI environment."`
- `"CMake version 3.16.0 is below minimum 3.20.0. Update CMake in your CI environment."`

## Remediation

### build-system-exists
1. Add a `CMakeLists.txt` for CMake-based builds (recommended)
2. Or add a `Makefile` for Make-based builds
3. Or add `meson.build` for Meson-based builds

### min-cpp-standard
1. In CMakeLists.txt: `set(CMAKE_CXX_STANDARD 17)` or `set(CMAKE_CXX_STANDARD 20)`
2. Or add compiler flags: `-std=c++17` or `-std=c++20`
3. Test thoroughly after upgrading — newer standards may deprecate features

### cppcheck-clean
1. Run `cppcheck --enable=all .` to see all warnings
2. Fix the reported issues (uninitialized variables, memory leaks, etc.)
3. For false positives, use `// cppcheck-suppress <id>` inline comments
4. If more warnings are acceptable, increase `max_cppcheck_warnings` threshold

### min-compiler-version-cicd
1. Update your CI/CD pipeline to use a newer gcc or clang
2. For GitHub Actions: update the compiler installation step
3. Newer compilers provide better diagnostics and C++ standard support

### min-cmake-version-cicd
1. Update CMake in your CI/CD pipeline
2. For GitHub Actions: use `lukka/get-cmake` or update the apt package
3. Modern CMake (3.20+) supports presets, better dependency management, and improved target handling
