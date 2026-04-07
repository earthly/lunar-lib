# Claude Collector

Detect Claude CLI usage in CI, discover instruction files, and run AI prompts against repository code.

## Overview

This collector captures Claude CLI invocations in CI pipelines with flag analysis, discovers CLAUDE.md instruction files across the repository, and can run custom Claude AI prompts against code for pattern detection and analysis.

Instruction file data writes to both `ai.native.claude.instruction_file` and normalized `ai.instructions.all[]` via array append. CI data writes to `ai.native.claude.cicd`. The prompt runner writes to a user-configurable Component JSON path.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.instructions.all[]` | array append | CLAUDE.md entry appended to the normalized instruction files array |
| `.ai.native.claude.instruction_file` | object | CLAUDE.md file: existence, path, line count, byte size, symlink status |
| `.ai.native.claude.cicd.cmds[]` | array | Claude CLI invocations in CI: command string, version, allowed/disallowed tools, MCP config |
| `{path}` (configurable) | any | Claude prompt response from run-prompt, optionally conforming to a JSON schema |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `instruction-file` | `code` | Discovers CLAUDE.md instruction files with metadata and symlink status |
| `cicd` | `ci-after-command` (binary: claude) | Captures Claude CLI invocations in CI with flag extraction |
| `run-prompt` | `code` | Runs a Claude AI prompt against the repo and collects structured results |

## Installation

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
