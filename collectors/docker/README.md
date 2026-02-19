# Docker Collector

Collects Docker container metadata from Dockerfiles and CI build commands.

## Overview

This collector analyzes Dockerfiles in the repository and intercepts `docker build` commands in CI. It extracts base images, labels, security configuration, build tags, and platform targeting. The collector outputs normalized data under `.containers` for container-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.containers.source` | object | Tool metadata (tool name and version) |
| `.containers.definitions[]` | array | Parsed Dockerfile definitions with base images, labels, and native AST |
| `.containers.builds[]` | array | CI build metadata (image, tag, labels, platform) |
| `.containers.native.docker.cicd` | object | Docker CI command tracking (commands + version) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `dockerfile` | Parses Dockerfiles to extract base images, users, healthchecks, and labels |
| `build-cicd` | Intercepts `docker build` commands in CI and collects build metadata |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find ./docker -name Dockerfile"  # Custom Dockerfile search
```
