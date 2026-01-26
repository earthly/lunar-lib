# `container` Policies

Enforces best practices for container definitions including tag stability, registry allowlists, required labels, and security configurations.

## Overview

This policy plugin validates container definitions (Dockerfiles, Containerfiles) against common best practices and security requirements. It helps ensure consistent, secure, and reproducible container builds across your organization.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `no-latest` | No `:latest` tags (explicit or implicit) | Image uses `:latest` tag (explicit or implicit) |
| `stable-tags` | Tags must be digests or full semver (e.g., `1.2.3`) | Image uses unstable tag (partial version, branch name, etc.) |
| `allowed-registries` | Images must come from allowed registries | Image pulled from registry not in allowlist |
| `required-labels` | Required labels must be present | Dockerfile missing one or more required labels |
| `healthcheck` | HEALTHCHECK instruction must be present | Final stage missing HEALTHCHECK instruction |
| `user` | USER instruction must be present | Final stage missing USER instruction |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.containers.definitions[]` | array | [`dockerfile`](https://github.com/earthly/lunar-lib/tree/main/collectors/dockerfile) collector |

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `allowed_registries` | `docker.io` | Comma-separated list of allowed registries |
| `required_labels` | `""` | Comma-separated list of required labels (empty = no requirement) |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github.com/earthly/lunar-lib/policies/container@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [no-latest, stable-tags]  # Only include specific policies
    # with:
    #   allowed_registries: "docker.io,gcr.io,ghcr.io"
    #   required_labels: "org.opencontainers.image.source"
```

## Examples

### Passing Example

```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          { "reference": "golang:1.21.5-alpine", "image": "golang", "tag": "1.21.5-alpine" },
          { "reference": "gcr.io/distroless/static:nonroot", "image": "gcr.io/distroless/static", "tag": "nonroot" }
        ],
        "final_stage": {
          "user": "nonroot",
          "has_healthcheck": true
        },
        "labels": {}
      }
    ]
  }
}
```

### Failing Examples

#### Using :latest tag (fails `no-latest`, `stable-tags`)
```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          { "reference": "node:latest", "image": "node", "tag": "latest" }
        ]
      }
    ]
  }
}
```

#### Using unstable tag (fails `stable-tags`)
```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          { "reference": "node:20-alpine", "image": "node", "tag": "20-alpine" }
        ]
      }
    ]
  }
}
```

#### Using disallowed registry (fails `allowed-registries`)
```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          { "reference": "my-private-registry.com/app:1.0.0", "image": "my-private-registry.com/app", "tag": "1.0.0" }
        ]
      }
    ]
  }
}
```

## Related Collectors

- [`dockerfile`](https://github.com/earthly/lunar-lib/tree/main/collectors/dockerfile) collector

## Remediation

### no-latest / stable-tags

Replace unstable tags with:
- **Digest** (most stable): `alpine@sha256:abc123...`
- **Full semver** (stable): `alpine:3.18.4`

Avoid:
- Implicit latest: `FROM alpine`
- Explicit latest: `FROM alpine:latest`
- Partial versions: `FROM node:20` or `FROM node:20-alpine`

### allowed-registries

Use images from approved registries only. Update your Dockerfile or request the registry be added to the allowlist.

### required-labels

Add the required labels to your Dockerfile:

```dockerfile
LABEL org.opencontainers.image.source="https://github.com/org/repo"
LABEL org.opencontainers.image.version="1.0.0"
```

### healthcheck

Add a HEALTHCHECK instruction:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost/health || exit 1
```

### user

Add a USER instruction to run as non-root:

```dockerfile
USER nonroot
# or
USER 1000:1000
```
