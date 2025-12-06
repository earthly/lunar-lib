# Collector README Template

Use this template when creating the `README.md` for a new collector plugin.

---

# {Collector Name}

> {One-line description of what this collector does}

## Overview

{2-3 sentences explaining what data this collector gathers, when it runs, and why it's useful.}

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.example.field` | boolean | Whether X exists |
| `.example.items` | array | List of Y found in the repository |
| `.example.details.count` | number | Count of Z |

<details>
<summary>Example Component JSON output</summary>

```json
{
  "example": {
    "field": true,
    "items": [
      {"name": "item1", "valid": true},
      {"name": "item2", "valid": false, "error": "..."}
    ],
    "details": {
      "count": 2
    }
  }
}
```

</details>

## Requirements

{List any requirements, or write "None" if there are no special requirements.}

- Requires `{tool}` to be available (installed via `install.sh`)
- Requires `{file}` to exist in the repository
- Requires secret `LUNAR_SECRET_{NAME}` to be configured

## Inputs

{If the collector has configurable inputs, list them here. If not, write "This collector has no configurable inputs."}

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `threshold` | No | `10` | Minimum threshold for X |
| `api_url` | Yes | - | Base URL for the external API |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/{path-to-collector}
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:                     # Uncomment if inputs are needed
    #   threshold: "20"
```

## Related Policies

{List any policies that consume this collector's data, or write "No specific policies required."}

This collector is typically used with:
- `{policy-name}` - {brief description}

---

## Template Usage Notes

When using this template:

1. Replace all `{placeholders}` with actual values
2. Remove sections that don't apply (e.g., Inputs if there are none)
3. Keep the "Example Component JSON output" in a collapsible `<details>` block
4. Be specific about the Component JSON paths - this is the contract with policies
5. Remove this "Template Usage Notes" section from the final README
