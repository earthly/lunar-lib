# Claude Guardrails

Claude-specific CI safety and conventions guardrails.

## Overview

This policy enforces Claude-specific CI standards. It validates that Claude CLI invocations in CI pipelines do not use dangerous permission-bypassing flags and use structured JSON output for deterministic automation.

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `cli-safe-flags` | error | Claude CLI must not use `--dangerously-skip-permissions` or similar flags |
| `cli-structured-output` | warning | Claude CLI in CI should use `--output-format json` |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.native.claude.cicd.cmds[]` | `claude` collector | Claude CLI invocations captured in CI |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/claude@main
    enforcement: report-pr
```

## Examples

### Passing

Claude CLI using safe flags and structured output:

```json
{
  "ai": {
    "native": {
      "claude": {
        "cicd": {
          "cmds": [
            {
              "cmd": "claude -p --output-format json --allowedTools Read 'review this PR'",
              "tool": "claude"
            }
          ]
        }
      }
    }
  }
}
```

### Failing

Claude CLI using dangerous permission-bypassing flag:

```json
{
  "ai": {
    "native": {
      "claude": {
        "cicd": {
          "cmds": [
            {
              "cmd": "claude --dangerously-skip-permissions -p 'deploy to prod'",
              "tool": "claude"
            }
          ]
        }
      }
    }
  }
}
```

## Remediation

- **cli-safe-flags**: Remove `--dangerously-skip-permissions` from Claude CI invocations. Use `--allowedTools` to grant specific tool access instead.
- **cli-structured-output**: Add `--output-format json` to Claude CLI invocations in CI.
