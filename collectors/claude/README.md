# Claude Collector

Detect Claude code review activity, CI usage, and run AI prompts against repository code.

## Overview

This collector provides comprehensive Claude integration: it detects Claude Code Review activity on pull requests by querying GitHub check-runs, captures Claude CLI invocations in CI pipelines with flag analysis, and can run custom Claude AI prompts against repository code for pattern detection and analysis.

Code review and CI data write to the unified `ai.*` namespace for tool-agnostic policy evaluation. The prompt runner writes to a user-configurable Component JSON path.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.code_reviewers[]` | array entry | Normalized code reviewer entry: tool name, check name, detection status, last seen timestamp |
| `.ai.native.claude.instruction_file` | object | CLAUDE.md file: existence, path, line count, byte size, symlink status |
| `.ai.native.claude.cicd.cmds[]` | array | Claude CLI invocations in CI: command string, version, allowed/disallowed tools, MCP config |
| `{path}` (configurable) | any | Claude prompt response from run-prompt, optionally conforming to a JSON schema |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `code-reviewer` | `code` (PRs only) | Detects Claude Code Review check-runs on PRs via GitHub API |
| `instruction-file` | `code` | Discovers CLAUDE.md instruction files with metadata and symlink status |
| `cicd` | `ci-after-command` (binary: claude) | Captures Claude CLI invocations in CI with flag extraction |
| `run-prompt` | `code` | Runs a Claude AI prompt against the repo and collects structured results |

## Installation

### Code Review + CI Detection

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```

### Run Prompt (AI-Powered Analysis)

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    include: [run-prompt]
    with:
      path: ".code_patterns.feature_flags"
      prompt: "Find all feature flags in this repository and return them as a list"
    secrets:
      ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}"
```

### With JSON Schema Enforcement

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: [backend]
    include: [run-prompt]
    with:
      path: ".code_patterns.lifecycle"
      prompt: "Analyze this codebase for graceful shutdown handling."
      json_schema: |
        {
          "type": "object",
          "properties": {
            "handles_sigterm": {"type": "boolean"},
            "shutdown_timeout_seconds": {"type": "number"},
            "files": {"type": "array", "items": {"type": "string"}}
          }
        }
    secrets:
      ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}"
```

