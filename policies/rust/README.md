# Rust Project Guardrails

Enforce Rust-specific project standards including Cargo manifest presence, lockfile requirements, edition and MSRV minimums, unsafe block limits, and clippy compliance.

## Overview

This policy validates Rust projects against best practices for crate management, safety, and code quality. It ensures projects have proper `Cargo.toml` and `Cargo.lock` files, use a modern Rust edition, limit unsafe code, and pass clippy linting.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `cargo-toml-exists` | Validates Cargo.toml exists | Project lacks crate manifest |
| `cargo-lock-exists` | Validates Cargo.lock for applications | Missing dependency lockfile |
| `min-rust-edition` | Ensures minimum Rust edition | Edition too old |
| `min-rust-version-cicd` | Ensures minimum Rust version in CI/CD | CI/CD Rust toolchain too old |
| `clippy-clean` | Ensures no clippy warnings | Clippy found code quality issues |
| `max-unsafe-blocks` | Limits unsafe block count | Too many unsafe blocks |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.rust` | object | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.cargo_toml_exists` | boolean | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.cargo_lock_exists` | boolean | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.edition` | string | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.is_application` | boolean | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.is_library` | boolean | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.unsafe_blocks` | object | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.cicd.cmds` | array | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |
| `.lang.rust.lint.warnings` | array | [`rust`](https://github.com/earthly/lunar-lib/tree/main/collectors/rust) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/rust@main
    on: [rust]  # Or use tags like ["domain:backend"]
    enforcement: report-pr
    # include: [cargo-toml-exists, cargo-lock-exists]  # Only run specific checks
    with:
      lock_mode: "auto"             # "auto", "required", "forbidden", "none" (default: "auto")
      min_rust_edition: "2021"      # Minimum Rust edition (default: "2021")
      min_rust_version_cicd: "1.75.0"  # Minimum Rust version in CI (default: "1.75.0")
      max_clippy_warnings: "0"      # Maximum clippy warnings allowed (default: "0")
      max_unsafe_blocks: "0"        # Maximum unsafe blocks allowed (default: "0")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "rust": {
      "edition": "2021",
      "cargo_toml_exists": true,
      "cargo_lock_exists": true,
      "is_application": true,
      "is_library": false,
      "unsafe_blocks": {
        "count": 0,
        "locations": []
      },
      "lint": {
        "warnings": []
      },
      "cicd": {
        "cmds": [
          { "cmd": "cargo test", "version": "1.77.0" }
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
    "rust": {
      "edition": "2018",
      "cargo_toml_exists": true,
      "cargo_lock_exists": false,
      "is_application": true,
      "is_library": false,
      "unsafe_blocks": {
        "count": 5,
        "locations": [
          {"file": "src/main.rs", "line": 10},
          {"file": "src/ffi.rs", "line": 22},
          {"file": "src/ffi.rs", "line": 45},
          {"file": "src/ffi.rs", "line": 78},
          {"file": "src/lib.rs", "line": 100}
        ]
      },
      "lint": {
        "warnings": [
          { "file": "src/main.rs", "line": 5, "message": "unused variable: `x`", "lint": "unused_variables" }
        ]
      }
    }
  }
}
```

**Failure messages:**
- `"Cargo.lock not found. Applications should commit Cargo.lock for reproducible builds. Run 'cargo generate-lockfile' to create it."`
- `"Rust edition 2018 is below minimum 2021. Update edition in Cargo.toml to '2021' or later."`
- `"5 unsafe blocks found, maximum allowed is 0. Reduce unsafe usage or increase the max_unsafe_blocks threshold."`
- `"1 clippy warning(s) found, maximum allowed is 0. Run 'cargo clippy' and fix all warnings."`

## Remediation

### cargo-toml-exists
1. Run `cargo init` to create a Cargo.toml file
2. Or `cargo new <project-name>` for a new project

### cargo-lock-exists
1. Run `cargo generate-lockfile` to create Cargo.lock
2. Commit it to version control (for applications)
3. For libraries, set `lock_mode: "none"` to skip this check

### min-rust-edition
1. Update `edition` in Cargo.toml: `edition = "2021"`
2. Run `cargo fix --edition` to automatically migrate code
3. Test thoroughly after edition migration

### min-rust-version-cicd
1. Update your CI/CD pipeline to use a newer Rust toolchain
2. For GitHub Actions: update `toolchain` in `dtolnay/rust-toolchain`
3. Update `rust-toolchain.toml` to pin the desired version

### clippy-clean
1. Run `cargo clippy` to see all warnings
2. Fix issues or apply suggested fixes with `cargo clippy --fix`
3. For false positives, add `#[allow(clippy::lint_name)]` with a comment explaining why

### max-unsafe-blocks
1. Review each unsafe block for necessity
2. Consider using safe abstractions or crates that encapsulate unsafe code
3. If unsafe is necessary, document the safety invariants with `// SAFETY:` comments
4. If more unsafe is needed, increase `max_unsafe_blocks` threshold with justification
