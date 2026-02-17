# Policy README Template

Use this template when creating the `README.md` for a new policy (guardrails).

---

# `{directory-name}` Guardrails

{One-line description of what this policy enforces}

## Overview

{2-3 sentences explaining what engineering standard this policy enforces, why it matters, and who should use it.}

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `example-check-1` | Validates X exists |
| `example-check-2` | Ensures Y meets threshold |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.example.field` | boolean | `example-collector` |
| `.example.items` | array | `example-collector` |

**Note:** Ensure the corresponding collector(s) are configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/{path-to-policy}@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    enforcement: report-pr      # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [example-check-1]  # Only run specific checks (omit to run all)
    # with:                       # Uncomment if inputs are needed
    #   minThreshold: "90"
```

## Examples

### Passing Example

{Show what a compliant component looks like.}

```json
{
  "example": {
    "field": true,
    "items": [{"name": "valid-item", "valid": true}]
  }
}
```

### Failing Example

{Show what triggers a failure and the expected message.}

```json
{
  "example": {
    "field": false
  }
}
```

**Failure message:** `"X is required but was not found"`

## Remediation

{Explain how to fix failures.}

When this policy fails, you can resolve it by:

1. {Step 1}
2. {Step 2}
3. {Step 3}

---

## Template Usage Notes

When using this template:

1. Replace all `{placeholders}` with actual values
2. Be specific about guardrail IDs - these appear in the Lunar UI
3. Always document the required Component JSON paths and which integration provides them
4. Include remediation steps - help developers fix issues
5. Remove this "Template Usage Notes" section from the final README
