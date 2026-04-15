# Claude Guardrails

Claude-specific CI safety and conventions guardrails.

## Overview

This policy enforces Claude-specific standards: CI safety flags, structured output, and CLAUDE.md symlink compatibility. It validates that Claude CLI invocations do not use dangerous flags, use structured JSON output, and that CLAUDE.md exists as a symlink to AGENTS.md.

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `cli-safe-flags` | error | Claude CLI must not use `--dangerously-skip-permissions` or similar flags |
| `cli-structured-output` | warning | Claude CLI in CI should use `--output-format json` |
| `symlinked-aliases` | warning | CLAUDE.md must exist as a symlink to AGENTS.md |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.native.claude.instruction_file` | `claude` collector | CLAUDE.md file detection with symlink status |
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
- **symlinked-aliases**: Create `ln -s AGENTS.md CLAUDE.md` so Claude Code can find the instruction file.
