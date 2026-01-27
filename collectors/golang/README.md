# `golang` Collector

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
| `.lang.go.native.golangci_lint` | object | Raw golangci-lint output and status |

**Note:** This collector writes Go-native coverage data to `.lang.go.tests.coverage`. For normalized cross-language coverage at `.testing.coverage`, use a dedicated coverage tool collector (CodeCov, Coveralls, etc.).

<details>
<summary>Example Component JSON output</summary>

```json
{
  "lang": {
    "go": {
      "module": "github.com/acme/myproject",
      "version": "1.21",
      "build_systems": ["go"],
      "native": {
        "go_mod": {
          "exists": true,
          "version": "1.21"
        },
        "go_sum": {
          "exists": true
        },
        "vendor": {
          "exists": false
        },
        "goreleaser": {
          "exists": true
        },
        "golangci_lint": {
          "passed": false,
          "config_exists": true,
          "exit_code": 1,
          "output": "main.go:42:5: unused variable 'x' (unused)"
        }
      },
      "source": {
        "tool": "go",
        "integration": "code"
      },
      "cicd": {
        "cmds": [
          {"cmd": "go test ./...", "version": "1.21.5"}
        ],
        "source": {
          "tool": "go",
          "integration": "ci"
        }
      },
      "tests": {
        "scope": "recursive",
        "coverage": {
          "percentage": 78.5,
          "profile_path": "coverage.out",
          "native": {
            "profile": "mode: set\ngithub.com/acme/myproject/main.go:10.2,12.16 1 1\n..."
          },
          "source": {
            "tool": "go cover",
            "integration": "ci"
          }
        }
      },
      "dependencies": {
        "direct": [
          {
            "path": "github.com/stretchr/testify",
            "version": "v1.8.4",
            "indirect": false,
            "replace": null
          }
        ],
        "transitive": [
          {
            "path": "github.com/davecgh/go-spew",
            "version": "v1.1.1",
            "indirect": true,
            "replace": null
          }
        ],
        "source": {
          "tool": "go mod",
          "integration": "code"
        }
      },
      "lint": {
        "warnings": [
          {
            "file": "main.go",
            "line": 42,
            "column": 5,
            "message": "unused variable 'x'",
            "linter": "unused"
          }
        ],
        "linters": ["golangci-lint"],
        "source": {
          "tool": "golangci-lint",
          "integration": "code"
        }
      }
    }
  }
}
```

</details>

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects Go project structure (go.mod, go.sum, vendor, goreleaser) |
| `dependencies` | code | Collects Go module dependency graph |
| `golangci-lint` | code | Runs golangci-lint and collects warnings |
| `cicd` | ci-before-command | Tracks Go commands run in CI with version info |
| `test-scope` | ci-before-command | Determines test scope (recursive vs package) |
| `test-coverage` | ci-after-command | Detects if go tests produced a coverage report and extracts results |

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `lint_timeout` | No | `5m` | Timeout for golangci-lint execution |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/golang@v1.0.0
    on: [go]  # Or use domain: ["domain:your-domain"]
    # include: [project, golangci-lint]  # Only include specific subcollectors
    # with:
    #   lint_timeout: "10m"
```

## Related Policies

None.
