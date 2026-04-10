# Shell Guardrails

Enforces shell script quality standards using ShellCheck lint data.

## Overview

This policy validates that ShellCheck runs cleanly against shell scripts in a component. It checks for errors and warnings, ensuring scripts follow best practices for portability, quoting, and correctness. Skips gracefully if no shell scripts are detected.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `shellcheck-clean` | Ensures no ShellCheck errors or warnings | ShellCheck found issues in shell scripts |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.shell` | object | [`shell`](https://github.com/earthly/lunar-lib/tree/main/collectors/shell) collector |
| `.lang.shell.lint.warnings` | array | [`shell`](https://github.com/earthly/lunar-lib/tree/main/collectors/shell) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/shell@main
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # with:
    #   max_shellcheck_warnings: "0"  # Maximum warnings allowed (default: "0")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "shell": {
      "script_count": 3,
      "shells": ["bash", "sh"],
      "lint": {
        "warnings": [],
        "linters": ["shellcheck"]
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "shell": {
      "script_count": 3,
      "shells": ["bash"],
      "lint": {
        "warnings": [
          {
            "file": "deploy.sh",
            "line": 15,
            "column": 3,
            "message": "Double quote to prevent globbing and word splitting.",
            "linter": "shellcheck",
            "severity": "warning",
            "code": "SC2086"
          }
        ],
        "linters": ["shellcheck"]
      }
    }
  }
}
```

**Failure message:** `"1 ShellCheck warning(s) found, maximum allowed is 0. Run 'shellcheck' on your scripts and fix all warnings."`

## Remediation

### shellcheck-clean
1. Run `shellcheck <script>.sh` locally to see all warnings
2. Fix the reported issues (quoting, unused variables, portability, etc.)
3. For false positives, use `# shellcheck disable=SC2086` inline directives
4. If some warnings are acceptable, increase `max_shellcheck_warnings` threshold
5. Alternatively, use the generic `linter` policy with `language: shell` and `max_warnings` for the same effect
