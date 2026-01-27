# `dockerfile` Collector

Parses Dockerfiles and collects container definition metadata including base images, final stage configuration, and labels.

## Overview

This collector finds all Dockerfiles in a repository and parses them using [dockerfile-json v1.2.2](https://github.com/keilerkonzept/dockerfile-json). It extracts structured information about container definitions including base images, user configuration, healthchecks, and labels. The collector runs on code changes and outputs normalized data for container-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.containers.source` | object | Tool metadata (tool name and version) |
| `.containers.definitions[]` | array | Parsed Dockerfile definitions with inline native AST |

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "containers": {
    "source": {
      "tool": "dockerfile-json",
      "version": "1.2.2"
    },
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          {
            "reference": "golang:1.21-alpine",
            "image": "golang",
            "tag": "1.21-alpine"
          },
          {
            "reference": "gcr.io/distroless/static-debian12:nonroot-amd64",
            "image": "gcr.io/distroless/static-debian12",
            "tag": "nonroot-amd64"
          }
        ],
        "final_stage": {
          "base_name": "runtime",
          "base_image": "gcr.io/distroless/static-debian12:nonroot-amd64",
          "user": "nonroot",
          "has_healthcheck": false
        },
        "labels": {
          "org.opencontainers.image.source": "https://github.com/acme/api"
        },
        "native": {
          "ast": { "Stages": ["..."] }
        }
      }
    ]
  }
}
```

</details>

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `find_command` | No | `find . -type f \( -name Dockerfile -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \)` | Command to find Dockerfiles (must output one file path per line) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dockerfile@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, containerized]
    # with:
    #   find_command: "find ./docker -name Dockerfile"  # Custom find command
```

## Related Policies

- [`container`](https://github.com/earthly/lunar-lib/tree/main/policies/container) - Container definition policies
