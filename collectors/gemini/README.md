# Gemini Collector

Detect Google Gemini CLI usage, instruction files, and CI invocations.

## Overview

This collector detects Google Gemini usage: discovers GEMINI.md instruction files and captures CLI invocations in CI pipelines. Writes to `ai.native.gemini` under the unified `ai.*` namespace.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.instructions.all[]` | array append | GEMINI.md entry appended to the normalized instruction files array |
| `.ai.native.gemini.instruction_file` | object | GEMINI.md file: existence, path, line count, byte size, symlink status |
| `.ai.native.gemini.cicd.cmds[]` | array | Gemini CLI invocations in CI: command string, version, and flags |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `instruction-file` | `code` | Discovers GEMINI.md instruction files with metadata and symlink status |
| `cicd` | `ci-after-command` (binary: gemini) | Captures Gemini CLI invocations in CI with flag extraction |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gemini@main
    on: ["domain:your-domain"]
```
