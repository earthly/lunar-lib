# Rust Collector

Collects Rust project information, CI/CD commands, test coverage, dependencies, unsafe block usage, and clippy results.

## Overview

This collector gathers metadata about Rust projects including crate information, dependency graphs, unsafe block tracking, test coverage metrics, and clippy lint results. It runs on both code changes (for static analysis) and CI hooks (to capture runtime metrics like test coverage).

**Note:** The CI-hook collectors (`test-coverage`, `cicd`) don't run tests—they observe and collect data from `cargo test` / `cargo tarpaulin` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.rust` | object | Rust project metadata (edition, MSRV, build systems) |
| `.lang.rust.build_systems` | array | Build systems detected (e.g., `["cargo"]`) |
| `.lang.rust.cargo_toml_exists` | boolean | Cargo.toml detected |
| `.lang.rust.cargo_lock_exists` | boolean | Cargo.lock detected |
| `.lang.rust.rust_toolchain_exists` | boolean | rust-toolchain.toml detected |
| `.lang.rust.clippy_configured` | boolean | Clippy config file detected |
| `.lang.rust.rustfmt_configured` | boolean | Rustfmt config file detected |
| `.lang.rust.edition` | string | Rust edition (`"2021"`, `"2024"`) |
| `.lang.rust.version` | string | Rust toolchain version |
| `.lang.rust.msrv` | string | Minimum Supported Rust Version from Cargo.toml |
| `.lang.rust.is_application` | boolean | Crate has binary targets |
| `.lang.rust.is_library` | boolean | Crate has a library target |
| `.lang.rust.workspace` | object/null | Workspace info (`is_workspace`, `members[]`) or null |
| `.lang.rust.unsafe_blocks` | object | Unsafe block count and locations |
| `.lang.rust.cicd` | object | CI/CD command tracking with Rust version |
| `.lang.rust.tests` | object | Test coverage information |
| `.lang.rust.dependencies` | object | Direct, dev, build, and transitive dependencies |
| `.lang.rust.lint` | object | Clippy lint results (passed, warnings) |
| `.lang.rust.lint.passed` | boolean | Whether clippy passed with no warnings |

**Note:** This collector writes Rust-native coverage data to `.lang.rust.tests.coverage`. For normalized cross-language coverage at `.testing.coverage`, use a dedicated coverage tool collector (CodeCov, Coveralls, etc.).

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure, edition, MSRV, unsafe blocks, workspace info |
| `dependencies` | code | Collects dependency graph from Cargo.toml and Cargo.lock |
| `clippy` | code | Runs cargo clippy and collects lint warnings |
| `cicd` | ci-before-command | Tracks cargo commands run in CI with version info |
| `test-coverage` | ci-after-command | Extracts coverage from cargo-tarpaulin or cargo-llvm-cov |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/rust@main
    on: [rust]  # Or use domain: ["domain:your-domain"]
    # include: [project, dependencies]  # Only include specific subcollectors
    # with:
    #   clippy_args: "-- -W clippy::pedantic"
```
