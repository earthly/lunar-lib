# Collector README Template

Use this template when creating the `README.md` for a new collector plugin.

---

# {Collector Name}

{One-line description of what this collector does}

## Overview

{2-3 sentences explaining what data this collector gathers, when it runs, and why it's useful.}

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.example.items[]` | array | List of Y found in the repository |
| `.example.native.{tool}` | object | Raw tool output for advanced policy use |

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "example": {
    "items": [
      {"name": "item1", "path": "src/item1.yaml"},
      {"name": "item2", "path": "src/item2.yaml", "error": "parse error"}
    ],
    "native": {
      "tool_name": { "...": "raw tool output" }
    }
  }
}
```

</details>

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `example-collector-1` | Checks for the existence of X |
| `example-collector-2` | Adds more data about Y |

## Inputs

{If the collector has configurable inputs, list them here. If not, write "This collector has no configurable inputs."}

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `threshold` | No | `10` | Minimum threshold for X |
| `api_url` | Yes | - | Base URL for the external API |

## Secrets

- `{secret-name}` - {brief description}

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/{path-to-collector}@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:                     # Uncomment if inputs are needed
    #   threshold: "20"
```

## Related Policies

This collector is typically used with:

- [`policy-name`](https://github.com/earthly/lunar-lib/tree/main/policies/policy-name) - Brief description of the policy

Or if no policies consume this data yet:

None.

---

## Template Usage Notes

When using this template:

1. Replace all `{placeholders}` with actual values
2. Remove sections that don't apply (e.g., Inputs if there are none)
3. Keep the "Example Component JSON output" in a collapsible `<details>` block
4. Only list top-level paths in the table (e.g., `.example.items[]`, `.example.summary`) - let the JSON example document the full nested structure
5. Remove this "Template Usage Notes" section from the final README
