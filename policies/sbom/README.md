# SBOM Guardrails

Enforces SBOM existence, license compliance, completeness, and format standards.

## Overview

This policy enforces Software Bill of Materials standards across your organization. It verifies that SBOMs are generated, contain license data, use approved formats, and keep licenses within an allow-list or out of a denylist. It works with data from both auto-generated SBOMs (via the syft collector) and CI-detected SBOMs, enabling vendor-agnostic SBOM governance.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `sbom-exists` | Checks that an SBOM was generated | No SBOM found from any source |
| `has-licenses` | Verifies components have license info | License coverage below threshold |
| `disallowed-licenses` | Checks for disallowed license patterns | Component uses a disallowed license |
| `allowed-licenses` | Checks component licenses against an allow-list | Component uses a license the allow-list does not admit |
| `min-components` | Verifies minimum component count | SBOM has too few components |
| `standard-format` | Validates SBOM format | SBOM uses a non-approved format |
| `blocked-origins` | Checks for license origin mentions from blocked countries | Dependency has country mention from blocklist |
| `disallowed-packages` | Checks for disallowed packages by PURL/name/group pattern | Package matches a disallowed pattern |

### How `allowed-licenses` evaluates licenses

- Every license a component carries is checked: CycloneDX `license.id`, `license.name` and `expression`, and SPDX `licenseConcluded` (falling back to `licenseDeclared`). A component that lists several licenses needs each of them allowed.
- SPDX expressions: `A OR B` passes if either side is allowed and `A AND B` needs both. `X WITH exception` passes if you list the full pair, or if `X` is allowed and the exception is on the [SPDX exceptions list](https://spdx.org/licenses/exceptions-index.html), whose entries only relax a license. So `Apache-2.0` admits `Apache-2.0 WITH LLVM-exception` but not `Apache-2.0 WITH Commons-Clause`. `X+` passes if `X` is allowed.
- Entries match the whole license ID, case-insensitively, as written or as a regex: `MIT` admits `MIT` but not `MIT-0`, and `BSD-.*-Clause` admits the BSD clause family. This differs from `disallowed_licenses`, which matches anywhere in the ID. A multi-word name that isn't an SPDX expression, such as `MIT License` or `MIT with modifications` (operators must be uppercase), is admitted only by an entry that matches it exactly.
- An SPDX `LicenseRef-…` is also admitted by the name it resolves to, so `Commercial` covers syft's CycloneDX `Commercial` and SPDX `LicenseRef-Commercial` alike.
- Components with no license data, including SPDX `NOASSERTION` and `NONE`, are left to `has-licenses` rather than failed twice.

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.sbom.auto` | object | `syft` collector (generate sub-collector) |
| `.sbom.cicd` | object | `syft` collector (ci sub-collector) |
| `.sbom.auto.cyclonedx.components` | array | `syft` collector |
| `.sbom.cicd.cyclonedx.components` | array | `syft` collector |
| `.sbom.cicd.spdx.packages` | array | `syft` collector (for `allowed-licenses`) |
| `.sbom.license_origins.packages` | array | `license-origins` collector (for `blocked-origins` check) |

**Note:** Ensure the `syft` collector is configured before enabling this policy. The `blocked-origins` check additionally requires the `license-origins` collector.

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
      # allowed_licenses: '["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"]'
      min_license_coverage: "90"
      min_components: "1"
      # allowed_formats: "cyclonedx"
      # disallowed_packages: '["alibabacloud", "aliyun-.*", ".*\\.ru$"]'
```

> **Tip:** `disallowed_licenses`, `allowed_licenses` and `disallowed_packages` accept either a comma-separated string (`"GPL.*,AGPL.*"`) or a JSON array string (`'["GPL.*", "AGPL.*"]'`). JSON arrays are recommended when patterns contain commas or complex regex.

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

### Failing Example (allowed-licenses)

With `allowed_licenses: '["MIT", "Apache-2.0"]'`, `jszip` passes because MIT is one of its alternatives, while `pako` needs Zlib as well:

```json
{
  "sbom": {
    "auto": {
      "cyclonedx": {
        "components": [
          { "name": "jszip", "version": "3.10.1", "licenses": [{ "expression": "MIT OR GPL-3.0-or-later" }] },
          { "name": "pako", "version": "1.0.11", "licenses": [{ "expression": "MIT AND Zlib" }] }
        ]
      }
    }
  }
}
```

**Failure message:** `"License 'MIT AND Zlib' is not in allowed_licenses: pako@1.0.11"`

## Remediation

When this policy fails, you can resolve it by:

1. **`sbom-exists` failure:** Enable the `syft` collector or run Syft in your CI pipeline to generate an SBOM
2. **`has-licenses` failure:** Ensure Syft has network access for remote license lookups, or add license metadata to your project dependencies
3. **`disallowed-licenses` failure:** Replace the disallowed dependency with an alternative that uses an approved license, or update the `disallowed_licenses` input
4. **`allowed-licenses` failure:** Replace the dependency, or add its license to `allowed_licenses` once it has been approved
5. **`min-components` failure:** Verify Syft can detect your project's package manager and dependencies are declared correctly
6. **`standard-format` failure:** Configure Syft to output in an approved format (e.g., `cyclonedx-json`) or update the `allowed_formats` input
7. **`blocked-origins` failure:** Review the flagged package's license file to confirm the country mention is genuine (not a false positive), then either replace the dependency or update the `blocked_countries`/`allowed_countries` inputs
8. **`disallowed-packages` failure:** Replace the disallowed dependency or update the `disallowed_packages` regex patterns
