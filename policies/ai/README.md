# AI Guardrails

Cross-tool AI guardrails for code review and tooling standards.

## Overview

This policy enforces AI tool standards across your organization using normalized data from tool-specific collectors. It checks that AI code review bots are active on pull requests, regardless of which specific tool is in use.

The policy reads from the `ai.code_reviewers[]` array, which is populated by tool-specific collectors (`coderabbit`, `claude`). Future subpolicies can be added here for other cross-tool AI checks (e.g., authorship validation, instruction file requirements).

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `code-reviewer` | error | At least one AI code reviewer must be active (any entry in `ai.code_reviewers[]` with `detected: true`) |

### code-reviewer

**What it checks:** The `ai.code_reviewers[]` array must contain at least one entry with `detected: true`.

**When it fails:** No AI code reviewer is detected on the component. This means no tool-specific collector (coderabbit, claude, etc.) has found an active code review bot.

**When it skips:** No `ai.code_reviewers` data exists at all — this means no tool-specific collectors are configured, so the check is not applicable.

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.code_reviewers[]` | `coderabbit` collector, `claude` collector | Normalized array of detected code review tools |

## Installation

Add to your `lunar-config.yml`:

```yaml
# First, enable at least one tool-specific collector:
collectors:
  - uses: github://earthly/lunar-lib/collectors/coderabbit@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"

  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"

# Then enable the policy:
policies:
  - uses: github://earthly/lunar-lib/policies/ai@main
    enforcement: report-pr
```

## Examples

### Passing

Component has an active code reviewer:

```json
{
  "ai": {
    "code_reviewers": [
      {
        "tool": "coderabbit",
        "check_name": "coderabbitai",
        "detected": true,
        "last_seen": "2024-01-15T10:30:00Z"
      }
    ]
  }
}
```

### Failing

Component has code reviewer data but none are active:

```json
{
  "ai": {
    "code_reviewers": [
      {
        "tool": "coderabbit",
        "check_name": "coderabbitai",
        "detected": false,
        "last_seen": "2023-06-01T12:00:00Z"
      }
    ]
  }
}
```

### Skipped

No code reviewer data exists (no tool-specific collectors configured):

```json
{
  "ai": {}
}
```

## Remediation

If the `code-reviewer` check fails:

1. **Enable a code review bot** on your repository (CodeRabbit, Claude Code Review, etc.)
2. **Configure the matching collector** in your `lunar-config.yml` to detect the tool
3. **Verify the bot is active** — open a PR and confirm the review bot posts checks
