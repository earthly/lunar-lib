# Gemini Collector

Detect Google Gemini CLI usage in CI pipelines.

## Overview

This collector detects Google Gemini CLI invocations in CI pipelines, recording command strings, versions, and flags for policy-level analysis. Writes to `ai.native.gemini` under the unified `ai.*` namespace.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ai.native.gemini.cicd.cmds[]` | array | Gemini CLI invocations in CI: command string, version, and flags |

## Collectors

This integration provides the following collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `cicd` | `ci-after-command` (binary: gemini) | Captures Gemini CLI invocations in CI with flag extraction |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gemini@main
    on: ["domain:your-domain"]
```
