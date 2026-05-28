# Go Collector

Collects Go project information, CI/CD commands, test coverage, dependencies, and linting results.

## Overview

This collector gathers metadata about Go projects including module information, dependency graphs, test coverage metrics, and golangci-lint results. It runs on both code changes (for static analysis) and CI hooks (to capture runtime metrics like test coverage).

**Note:** The CI-hook collectors (`test-coverage`, `test-scope`, `cicd`) don't run tests—they observe and collect data from `go test` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.go` | object | Go project metadata (module, version, build systems) |
| `.lang.go.module` | string | Go module path (e.g., `github.com/acme/myproject`) |
| `.lang.go.cicd` | object | CI/CD command tracking with Go version |
| `.lang.go.tests` | object | Test scope and coverage information |
| `.lang.go.dependencies` | object | Direct and transitive dependencies |
| `.lang.go.lint` | object | Normalized lint warnings from golangci-lint |
| `.lang.go.golangci_lint` | object | Raw golangci-lint output and status |

**Note:** This collector writes Go-native coverage data to `.lang.go.tests.coverage`. For normalized cross-language coverage at `.testing.coverage`, use a dedicated coverage tool collector (CodeCov, Coveralls, etc.).

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects Go project structure (go.mod, go.sum, vendor, goreleaser) |
| `dependencies` | code | Collects Go module dependency graph |
| `golangci-lint` | code | Runs golangci-lint and collects warnings |
| `golangci-lint-ci` | ci-after-command | Detects user-invoked `golangci-lint run` in CI and collects warnings |
| `cicd` | ci-before-command | Tracks Go commands run in CI with version info |
| `test-scope` | ci-before-command | Determines test scope (recursive vs package) |
| `test-coverage` | ci-after-command | Detects if go tests produced a coverage report and extracts results |

### Lint data sources: code-hook vs CI-hook

Two sub-collectors write to `.lang.go.lint`:

- `golangci-lint` (code hook) runs the linter itself in a container. Heavyweight, requires the `golang-main` image, and has known memory limitations on large codebases.
- `golangci-lint-ci` (ci-after-command hook) passively observes `golangci-lint run` invocations in the user's CI pipeline. Zero runtime cost; gets full warnings when the user emits JSON output.

Pick **one** based on whether you already run golangci-lint in CI:

- **You already run golangci-lint in CI** → use `golangci-lint-ci` (cheaper, mirrors CI behavior exactly). Recommended.
- **You don't run it in CI and want Lunar to lint for you** → use `golangci-lint` (code hook).

For full warning detail from the CI-hook variant, invoke golangci-lint with JSON output:

```yaml
# .github/workflows/ci.yml
- run: golangci-lint run --output.json.path=lint.json --output.text.path=stdout
```

Without JSON output, the CI-hook still records that linting ran (satisfies the `linter/ran` policy) but cannot populate per-warning detail.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/golang@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, golangci-lint]  # Only include specific subcollectors
    # with:
    #   lint_timeout: "10m"
```
