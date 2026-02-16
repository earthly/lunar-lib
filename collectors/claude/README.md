# Claude Collector

Run Claude AI prompts against repository code and collect structured results for policy evaluation.

## Overview

This collector executes Claude AI prompts against your repository to extract insights, detect patterns, and analyze code that's difficult to capture with traditional pattern matching. It runs on code changes and writes results to a configurable Component JSON path.

Use cases include:
- Feature flag detection and inventory
- Documentation quality analysis
- Graceful shutdown handling verification
- Architecture pattern detection
- API documentation completeness checks

## Collected Data

This collector writes to a user-specified Component JSON path via the `path` input:

| Path | Type | Description |
|------|------|-------------|
| `{path}` | any | Claude's response, optionally conforming to a JSON schema |

## Collectors

This integration provides the following collector:

| Collector | Description |
|-----------|-------------|
| `claude` | Runs a Claude prompt and collects structured results |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@v1.0.0
    on: ["domain:your-domain"]
    with:
      path: ".code_patterns.feature_flags"
      prompt: "Find all feature flags in this repository and return them as a list"
```

### With JSON Schema Enforcement

For structured output, provide a JSON schema:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/claude@v1.0.0
    on: [backend]
    with:
      path: ".code_patterns.lifecycle"
      prompt: "Analyze this codebase for graceful shutdown handling. Check if SIGTERM signals are properly handled."
      json_schema: |
        {
          "type": "object",
          "properties": {
            "handles_sigterm": {"type": "boolean"},
            "shutdown_timeout_seconds": {"type": "number"},
            "files": {"type": "array", "items": {"type": "string"}}
          }
        }
```
