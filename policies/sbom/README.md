# SBOM Guardrails

Enforces SBOM existence, license compliance, completeness, and format standards.

## Overview

This policy enforces Software Bill of Materials standards across your organization. It verifies that SBOMs are generated, contain license data, use approved formats, and do not include disallowed licenses. It works with data from both auto-generated SBOMs (via the syft collector) and CI-detected SBOMs, enabling vendor-agnostic SBOM governance.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `sbom-exists` | Checks that an SBOM was generated | No SBOM found from any source |
| `has-licenses` | Verifies components have license info | License coverage below threshold |
| `disallowed-licenses` | Checks for disallowed license patterns | Component uses a disallowed license |
| `min-components` | Verifies minimum component count | SBOM has too few components |
| `standard-format` | Validates SBOM format | SBOM uses a non-approved format |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.sbom.auto` | object | `syft` collector (generate sub-collector) |
| `.sbom.cicd` | object | `syft` collector (ci sub-collector) |
| `.sbom.auto.cyclonedx.components` | array | `syft` collector |
| `.sbom.cicd.cyclonedx.components` | array | `syft` collector |

**Note:** Ensure the `syft` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sbom@main
    on: ["domain:engineering"]
    enforcement: block-pr
    # include: [sbom-exists, disallowed-licenses]
    with:
      disallowed_licenses: "GPL.*,BSL.*,AGPL.*"
      min_license_coverage: "90"
      min_components: "1"
      # allowed_formats: "cyclonedx"
```

## Examples

### Passing Example

All components have approved licenses and license coverage meets the threshold:

```json
{
  "sbom": {
    "auto": {
      "source": { "tool": "syft", "integration": "code", "version": "1.19.0" },
      "cyclonedx": {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [
          {
            "name": "github.com/sirupsen/logrus",
            "version": "v1.9.3",
            "licenses": [{ "license": { "id": "MIT" } }]
          }
        ]
      }
    }
  }
}
```

### Failing Example

A component uses a disallowed GPL license:

```json
{
  "sbom": {
    "auto": {
      "cyclonedx": {
        "components": [
          {
            "name": "copyleft-lib",
            "licenses": [{ "license": { "id": "GPL-3.0" } }]
          }
        ]
      }
    }
  }
}
```

**Failure message:** `"Component 'copyleft-lib' uses disallowed license 'GPL-3.0' (matches pattern 'GPL.*')"`

## Remediation

When this policy fails, you can resolve it by:

1. **`sbom-exists` failure:** Enable the `syft` collector or run Syft in your CI pipeline to generate an SBOM
2. **`has-licenses` failure:** Ensure Syft has network access for remote license lookups, or add license metadata to your project dependencies
3. **`disallowed-licenses` failure:** Replace the disallowed dependency with an alternative that uses an approved license, or update the `disallowed_licenses` input
4. **`min-components` failure:** Verify Syft can detect your project's package manager and dependencies are declared correctly
5. **`standard-format` failure:** Configure Syft to output in an approved format (e.g., `cyclonedx-json`) or update the `allowed_formats` input
