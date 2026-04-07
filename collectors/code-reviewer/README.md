# Code Reviewer Detector

Detect AI code review tools active on pull requests.

## Overview

This collector detects AI-powered code review tools running on pull requests by querying the GitHub check-runs API. Currently detects Claude Code Review; the architecture supports adding detection for additional tools (e.g., CodeRabbit, Copilot) as subcollectors.

Writes to the normalized `ai.code_reviewers[]` array so the ai policy can enforce code review presence without caring which specific tool is active.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.code_reviewers[]` | array entry | Normalized code reviewer entry: tool name, check name, detection status, last seen timestamp |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `claude` | `code` (PRs only) | Detects Claude Code Review check-runs on PRs via GitHub API |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/code-reviewer@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```
