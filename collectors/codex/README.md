# Codex Collector

Detect OpenAI Codex CLI usage, instruction files, and CI invocations.

## Overview

This collector detects OpenAI Codex usage: discovers CODEX.md instruction files and captures CLI invocations in CI pipelines. Writes to `ai.native.codex` under the unified `ai.*` namespace.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.instructions.all[]` | array append | CODEX.md entry appended to the normalized instruction files array |
| `.ai.native.codex.instruction_file` | object | CODEX.md file: existence, path, line count, byte size, symlink status |
| `.ai.native.codex.cicd.cmds[]` | array | Codex CLI invocations in CI: command string, version, and flags |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `instruction-file` | `code` | Discovers CODEX.md instruction files with metadata and symlink status |
| `cicd` | `ci-after-command` (binary: codex) | Captures Codex CLI invocations in CI with flag extraction |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codex@main
    on: ["domain:your-domain"]
```
