# Claude Collector

Detect Claude code review activity, CI usage, instruction files, and run AI prompts against repository code.

## Overview

This collector detects Claude Code Review on pull requests, captures Claude CLI invocations in CI pipelines, discovers CLAUDE.md instruction files, and can run custom Claude AI prompts or code review against PRs.

Code reviewer data writes to normalized `ai.code_reviewers[]`. Instruction file data writes to both `ai.native.claude.instruction_file` and normalized `ai.instructions.all[]` via array append. CI data writes to `ai.native.claude.cicd`. The run-code-review subcollector writes to `ai.native.claude.code_review`. The prompt runner writes to a user-configurable Component JSON path.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.code_reviewers[]` | array append | Claude Code Review detection entry with check name and timestamp |
| `.ai.instructions.all[]` | array append | CLAUDE.md entry appended to the normalized instruction files array |
| `.ai.native.claude.instruction_file` | object | CLAUDE.md file: existence, path, line count, byte size, symlink status |
| `.ai.native.claude.cicd.cmds[]` | array | Claude CLI invocations in CI: command string, version, allowed/disallowed tools, MCP config |
| `.ai.native.claude.code_review` | object | Claude CLI review mode results: findings count, severity, affected files |
| `{path}` (configurable) | any | Claude prompt response from run-prompt, optionally conforming to a JSON schema |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `code-reviewer` | `code` (PRs only) | Detects Claude Code Review check-runs on pull requests |
| `run-code-review` | `code` (PRs only) | Runs Claude CLI in review mode against PR diffs |
| `instruction-file` | `code` | Discovers CLAUDE.md instruction files with metadata and symlink status |
| `cicd` | `ci-after-command` (binary: claude) | Captures Claude CLI invocations in CI with flag extraction |
| `run-prompt` | `code` | Runs a Claude AI prompt against the repo and collects structured results |

## Installation

### Code Review Detection

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    include: [code-reviewer]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```

### Run Code Review (AI-Powered)

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
    include: [run-code-review]
    secrets:
      ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}"
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"
```

### CI Detection + Instruction Files

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@main
    on: ["domain:your-domain"]
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
