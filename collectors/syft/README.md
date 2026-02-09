# Syft SBOM Collector

Generate or detect CycloneDX/SPDX SBOMs using Anchore Syft.

## Overview

This collector generates Software Bill of Materials (SBOMs) automatically using Syft, or detects existing Syft runs in CI pipelines. It supports CycloneDX and SPDX formats with remote license detection for Go, Java, Node.js, and Python projects. The `generate` sub-collector runs on every code push, while the `ci` sub-collector detects when Syft is already part of your CI pipeline.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.auto.source` | object | Source metadata for auto-generated SBOMs |
| `.sbom.auto.cyclonedx` | object | Full CycloneDX JSON from auto-generation |
| `.sbom.cicd.source` | object | Source metadata for CI-detected SBOMs |
| `.sbom.cicd.cyclonedx` | object | CycloneDX JSON collected from CI output |
| `.sbom.cicd.spdx` | object | SPDX JSON collected from CI output |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `generate` | Auto-generates a CycloneDX SBOM using Syft (code hook) |
| `ci` | Detects Syft execution in CI pipelines (ci-after-command hook) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/syft@main
    on: ["domain:engineering"]
```
