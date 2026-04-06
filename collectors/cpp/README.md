# C/C++ Collector

Collects C/C++ project information, build system details, dependencies, and CI commands.

## Overview

This collector gathers metadata about C/C++ projects including build system detection (CMake, Make, Meson, Autotools, Bazel), source file inventory, C++ standard version, package manager dependencies (Conan, vcpkg), optional cppcheck static analysis, and CI/CD compiler command tracking.

**Note:** The cppcheck sub-collector only runs if cppcheck is available in the image. The CI-hook collectors (`cicd`, `cmake-cicd`) don't compile code—they observe and collect data from compiler/build commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.cpp` | object | C/C++ project metadata (build systems, source files, standards) |
| `.lang.cpp.build_systems` | array | Detected build systems (e.g., `["cmake", "make"]`) |
| `.lang.cpp.cpp_standard` | string | C++ standard version (e.g., `"17"`, `"20"`) |
| `.lang.cpp.source_files` | object | Source file counts by type (c, cpp, headers) |
| `.lang.cpp.dependencies` | object | Dependencies from Conan, vcpkg, and CMake find_package |
| `.lang.cpp.lint` | object | Normalized lint warnings from cppcheck |
| `.lang.cpp.native.cppcheck` | object | Raw cppcheck output and status |
| `.lang.cpp.cicd` | object | CI/CD compiler and build command tracking |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects build systems, source files, C++ standard version |
| `dependencies` | code | Extracts dependencies from Conan, vcpkg, and CMake |
| `cppcheck` | code | Runs cppcheck static analysis (if available) |
| `cicd` | ci-before-command | Tracks C/C++ compiler commands in CI |
| `cmake-cicd` | ci-before-command | Tracks CMake commands in CI |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/cpp@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```
