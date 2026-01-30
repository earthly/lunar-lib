# Go Project Policies

Enforce Go-specific project standards including module configuration, Go version requirements, test execution scope, and vendoring policies.

## Overview

This policy validates Go projects against best practices for module management and project structure. It ensures projects have proper `go.mod` and `go.sum` files, use a minimum Go version, run tests recursively to cover all packages, and follow your team's vendoring standards.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `go-mod-exists` | Validates go.mod exists | Project lacks module definition |
| `go-sum-exists` | Validates go.sum exists | Missing dependency checksums |
| `min-go-version` | Ensures minimum Go version | Go version too old |
| `tests-recursive` | Ensures tests run with `./...` | Tests may miss subpackages |
| `vendoring` | Enforces vendoring policy | Vendor dir present/absent per policy |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.go` | object | `golang` collector |
| `.lang.go.native.go_mod.exists` | boolean | `golang` collector |
| `.lang.go.native.go_sum.exists` | boolean | `golang` collector |
| `.lang.go.version` | string | `golang` collector |
| `.lang.go.tests.scope` | string | `golang` collector |
| `.lang.go.native.vendor.exists` | boolean | `golang` collector |

**Note:** Ensure the `golang` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github.com/earthly/lunar-lib/policies/golang@v1.0.0
    on: [go]  # Or use tags like ["domain:backend"]
    enforcement: report-pr  # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [go-mod-exists, go-sum-exists]  # Only run specific checks (omit to run all)
    with:
      min_go_version: "1.21"
      vendoring_mode: "none"  # Options: required, forbidden, none
```

## Configuration

| Input | Default | Description |
|-------|---------|-------------|
| `min_go_version` | `"1.21"` | Minimum required Go version |
| `vendoring_mode` | `"none"` | `"required"`, `"forbidden"`, or `"none"` (skip) |

## Examples

### Passing Example

```json
{
  "lang": {
    "go": {
      "module": "github.com/acme/myproject",
      "version": "1.22",
      "native": {
        "go_mod": { "exists": true },
        "go_sum": { "exists": true },
        "vendor": { "exists": false }
      },
      "tests": {
        "scope": "recursive"
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "go": {
      "version": "1.19",
      "native": {
        "go_mod": { "exists": false },
        "go_sum": { "exists": false }
      }
    }
  }
}
```

**Failure messages:**
- `"go.mod not found. Initialize with 'go mod init <module-path>'"`
- `"go.sum not found. Run 'go mod tidy' to generate checksums."`
- `"Go version 1.19 is below minimum 1.21. Update go.mod to require Go 1.21 or higher."`

## Remediation

When this policy fails, you can resolve it by:

### go-mod-exists
1. Run `go mod init <module-path>` to create a go.mod file
2. The module path should match your repository URL (e.g., `github.com/org/repo`)

### go-sum-exists
1. Run `go mod tidy` to generate the go.sum file
2. Commit the go.sum file to version control

### min-go-version
1. Update the `go` directive in your go.mod file: `go 1.21`
2. Run `go mod tidy` to update dependencies
3. Test your code with the new Go version

### tests-recursive
1. Update your CI configuration to run `go test ./...` instead of targeting specific packages
2. This ensures all packages and subpackages are tested

### vendoring
- If `vendoring_mode: required`: Run `go mod vendor` to create the vendor directory
- If `vendoring_mode: forbidden`: Remove the `vendor/` directory from your repository
