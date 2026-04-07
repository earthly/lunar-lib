# Codex Collector

Detect OpenAI Codex CLI usage in CI pipelines.

## Overview

This collector detects OpenAI Codex CLI invocations in CI pipelines, recording command strings, versions, and flags for policy-level analysis. Writes to `ai.native.codex` under the unified `ai.*` namespace.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.native.codex.cicd.cmds[]` | array | Codex CLI invocations in CI: command string, version, and flags |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `cicd` | `ci-after-command` (binary: codex) | Captures Codex CLI invocations in CI with flag extraction |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codex@main
    on: ["domain:your-domain"]
```
