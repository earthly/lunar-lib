# Gemini Guardrails

Gemini-specific CI safety and conventions guardrails.

## Overview

This policy enforces Gemini-specific CI standards. It validates that Gemini CLI invocations in CI pipelines do not use dangerous permission-bypassing flags and use structured JSON output for deterministic automation.

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `cli-safe-flags` | error | Gemini CLI must not use `--yolo` or `-y` flags |
| `cli-structured-output` | warning | Gemini CLI in CI should use structured JSON output |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.native.gemini.cicd.cmds[]` | `gemini` collector | Gemini CLI invocations captured in CI |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gemini@main
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/gemini@main
    enforcement: report-pr
```

## Examples

### Passing

Gemini CLI using safe flags and structured output:

```json
{
  "ai": {
    "native": {
      "gemini": {
        "cicd": {
          "cmds": [
            {
              "cmd": "gemini run --json 'review this PR'",
              "tool": "gemini"
            }
          ]
        }
      }
    }
  }
}
```

### Failing

Gemini CLI using dangerous flag:

```json
{
  "ai": {
    "native": {
      "gemini": {
        "cicd": {
          "cmds": [
            {
              "cmd": "gemini run --yolo 'deploy to prod'",
              "tool": "gemini"
            }
          ]
        }
      }
    }
  }
}
```

## Remediation

- **cli-safe-flags**: Remove `--yolo` and `-y` from Gemini CI invocations. Use scoped permissions instead.
- **cli-structured-output**: Add `--json` or equivalent structured output flag to Gemini CLI invocations in CI.
