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
  - uses: github.com/earthly/lunar-lib/collectors/claude@v1.0.0
    on: ["domain:your-domain"]
    with:
      path: ".claude.feature_flags"
      prompt: "Find all feature flags in this repository and return them as a list"
```

### With JSON Schema Enforcement

For structured output, provide a JSON schema:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/claude@v1.0.0
    on: [backend]
    with:
      path: ".claude.graceful_shutdown"
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

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `path` | Yes | JSON component path to write results to (e.g., `.claude.analysis`) |
| `prompt` | Yes | The prompt for Claude to execute against the repository |
| `json_schema` | No | JSON schema for structured output enforcement |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude authentication |

Configure the secret in your Lunar configuration:

```yaml
secrets:
  ANTHROPIC_API_KEY:
    source: env  # or: vault, aws-secrets-manager, etc.
```

## Example Usage

### Feature Flag Inventory

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/claude@v1.0.0
    on: [backend]
    with:
      path: ".claude.feature_flags"
      prompt: |
        Find all feature flags in this repository. Look for:
        - LaunchDarkly flags
        - Unleash flags
        - Custom feature flag implementations
        Return the flag names, their locations, and any documentation.
      json_schema: |
        {
          "type": "object",
          "properties": {
            "flags": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "name": {"type": "string"},
                  "file": {"type": "string"},
                  "line": {"type": "number"},
                  "documented": {"type": "boolean"}
                }
              }
            },
            "total_count": {"type": "number"}
          }
        }
```

### Runbook Completeness Check

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/claude@v1.0.0
    on: [tier1]
    with:
      path: ".claude.runbook_analysis"
      prompt: |
        Analyze the runbook documentation in this repository (look in docs/, runbooks/, or README files).
        Check if it contains:
        - Incident response procedures
        - Escalation contacts
        - Recovery steps
        - Monitoring dashboard links
```

## When to Use Claude vs. ast-grep

| Use Case | Recommended Tool |
|----------|------------------|
| Syntax-aware pattern matching | ast-grep |
| Finding specific code patterns | ast-grep |
| Understanding code semantics | Claude |
| Documentation analysis | Claude |
| Complex multi-file analysis | Claude |
| High-volume, low-latency checks | ast-grep |

## Limitations

- Requires an Anthropic API key
- API calls add latency to collection
- Token limits may affect analysis of very large repositories
- Results may vary between runs for non-deterministic prompts

