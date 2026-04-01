# Category: `.api`

API specifications. Technology-agnostic — holds data from any spec format (OpenAPI, Swagger, AsyncAPI, etc.) via the [Multi-Collector Category Aggregation](../strategies.md#strategy-17-multi-collector-category-aggregation) pattern.

```json
{
  "api": {
    "specs": [
      {
        "type": "openapi",
        "path": "api/openapi.yaml",
        "valid": true,
        "version": "3.0.3",
        "paths_count": 42,
        "schemas_count": 15
      },
      {
        "type": "swagger",
        "path": "swagger.json",
        "valid": true,
        "version": "2.0",
        "paths_count": 18,
        "schemas_count": 7
      }
    ],
    "source": {
      "tool": "openapi",
      "version": "1.0.0",
      "integration": "code"
    }
  }
}
```

## Key Policy Paths

- `.api.specs[]` — Array of detected spec files (presence = spec exists)
- `.api.specs[].type` — Spec format: `"openapi"` or `"swagger"`
- `.api.specs[].valid` — Spec parses without errors
- `.api.specs[].version` — Spec version string (e.g., `"3.0.3"`, `"2.0"`)
- `.api.specs[].paths_count` — Number of API endpoint paths
- `.api.specs[].schemas_count` — Number of schema definitions

## Collectors

| Collector | Writes | Detects |
|-----------|--------|---------|
| `openapi` | `.api.specs[]` | OpenAPI 3.x files (`openapi.yaml`, `openapi.yml`, `openapi.json`) |
| `swagger` | `.api.specs[]` | Swagger 2.0 files (`swagger.yaml`, `swagger.yml`, `swagger.json`) |

Both collectors write to the same `.api.specs[]` array. Lunar auto-merges them.

## Design Notes

This category uses **Strategy 17: Multi-Collector Category Aggregation**. Each spec format gets its own technology-specific collector, but they all feed the same `.api` category. The `api-docs` policy reads the merged array without caring which collector produced each entry. See [strategies.md](../strategies.md) for details.
