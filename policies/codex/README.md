# Codex Guardrails

Codex-specific CI safety and conventions guardrails.

## Overview

This policy enforces Codex-specific CI standards. It validates that Codex CLI invocations in CI pipelines do not use dangerous permission-bypassing flags and use structured JSON output for deterministic automation.

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `cli-safe-flags` | error | Codex CLI must not use `--full-auto` or similar flags |
| `cli-structured-output` | warning | Codex CLI in CI should use structured JSON output |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.native.codex.cicd.cmds[]` | `codex` collector | Codex CLI invocations captured in CI |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codex@main
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/codex@main
    enforcement: report-pr
```

## Examples

### Passing

Codex CLI using safe flags and structured output:

```json
{
  "ai": {
    "native": {
      "codex": {
        "cicd": {
          "cmds": [
            {
              "cmd": "codex exec --json 'review this PR'",
              "tool": "codex"
            }
          ]
        }
      }
    }
  }
}
```

### Failing

Codex CLI using dangerous flag:

```json
{
  "ai": {
    "native": {
      "codex": {
        "cicd": {
          "cmds": [
            {
              "cmd": "codex --full-auto 'deploy to prod'",
              "tool": "codex"
            }
          ]
        }
      }
    }
  }
}
```

## Remediation

- **cli-safe-flags**: Remove `--full-auto` from Codex CI invocations. Use scoped permissions instead.
- **cli-structured-output**: Add `--json` or equivalent structured output flag to Codex CLI invocations in CI.
