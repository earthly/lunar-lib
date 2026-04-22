# Category: `.catalog`

Service catalog entries. Reserved namespace for data from catalog tools (Backstage, ServiceNow, custom catalogs, etc.).

Each catalog tool writes its raw descriptor under `.catalog.native.<tool>`, following the same `.native` convention used by `.api.native.openapi`, `.iac.native.terraform`, and `.sbom.native.spdx`. This keeps multi-tool coexistence collision-free: a company running both Backstage and ServiceNow for different purposes lands each tool's data in its own `.catalog.native.<tool>` bucket without overwriting the other.

**Presence as the signal.** If a catalog tool finds no descriptor file, it writes nothing to component JSON — the absence of `.catalog.native.<tool>` means "this tool did not find data for this component." No redundant `exists: false` sentinel. Policies use `Check.exists(".catalog.native.<tool>")` to detect file-level presence.

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "valid": true,
        "errors": [],
        "path": "catalog-info.yaml",
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {
          "name": "payment-api",
          "description": "Payment processing API",
          "annotations": {
            "backstage.io/techdocs-ref": "dir:.",
            "pagerduty.com/integration-key": "PXXXXXX"
          },
          "tags": ["payments", "api"]
        },
        "spec": {
          "type": "service",
          "owner": "team-payments",
          "lifecycle": "production",
          "system": "payment-platform",
          "providesApis": ["payment-api"],
          "consumesApis": ["user-api"],
          "dependsOn": ["resource:database-payments"]
        }
      }
    }
  }
}
```

## Native Data

Each cataloger writes its raw descriptor verbatim under `.catalog.native.<tool>`. Annotations and tool-specific keys keep their original prefixes (e.g. `backstage.io/*`, vendor-specific). Policies targeting a specific catalog tool read from that tool's native path directly.

| Path | Type | Provided By |
|------|------|-------------|
| `.catalog.native.backstage` | object | `backstage` collector |
| `.catalog.native.servicenow` | object | future `servicenow` collector |

## Normalized Fields

**None currently.** Normalized top-level fields (e.g. `.catalog.exists`, `.catalog.owner`) were considered but not added — multi-catalog deployments run Backstage and ServiceNow for different purposes, not as interchangeable alternatives, so forcing a single normalized view would either require conflict-resolution config or silently drop one source's data.

If a future cataloger lands and a clear normalization pattern emerges (e.g. "`.catalog.catalogs[]` lists every tool this component is registered in"), add it here alongside the existing native data. Same escape hatch as `.api`, which also ships without a protocol-normalized layer and lets policies read `.api.native.*` directly.

## Key Policy Paths

- `.catalog.native.backstage` — namespace present ⇔ catalog-info.yaml was found (use `Check.exists(...)`)
- `.catalog.native.backstage.valid` — catalog-info.yaml passes lint checks
- `.catalog.native.backstage.spec.owner` — Owner defined in Backstage
- `.catalog.native.backstage.spec.lifecycle` — Lifecycle stage in Backstage
- `.catalog.native.backstage.spec.system` — System grouping in Backstage
