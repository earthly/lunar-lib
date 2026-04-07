# Run Code Review

Run AI-powered code review on pull requests.

## Overview

This collector actively runs an AI code review on pull request diffs using the Claude CLI in review mode. Unlike the `code-reviewer` collector (which passively detects existing review tools), this collector executes the review and captures findings.

Results are written to `ai.native.claude.code_review` for policy evaluation. Future subcollectors could support additional AI review tools.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.native.claude.code_review` | object | Review results: whether it ran, finding count, and individual findings with severity, file, line, and message |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `claude` | `code` (PRs only) | Runs Claude CLI in review mode against PR diffs |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/run-code-review@main
    on: ["domain:your-domain"]
    secrets:
      ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}"
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```
