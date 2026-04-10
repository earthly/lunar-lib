# Docker Collector

Collects Docker container metadata from Dockerfiles, CI build commands, and Dockerfile lint results.

## Overview

This collector analyzes Dockerfiles in the repository, intercepts `docker build` commands in CI, and auto-runs hadolint to lint Dockerfiles. It extracts base images, labels, security configuration, build tags, platform targeting, and lint violations. The collector outputs normalized data under `.containers` for container-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.containers.source` | object | Tool metadata (tool name and version) |
| `.containers.definitions[]` | array | Parsed Dockerfile definitions with base images, labels, and native AST |
| `.containers.lint_results[]` | array | Normalized lint results per Dockerfile (rule, severity, message, line) |
| `.containers.builds[]` | array | CI build metadata (image, tag, labels, platform) |
| `.containers.native.docker.cicd` | object | Docker CI command tracking (commands + version) |
| `.containers.native.hadolint` | object | Raw hadolint JSON output with source metadata |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `dockerfile` | Parses Dockerfiles to extract base images, users, healthchecks, and labels |
| `cicd` | Tracks all docker commands in CI; parses build metadata for `docker build` |
| `hadolint` | Lints Dockerfiles using hadolint and collects violations |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find ./docker -name Dockerfile"  # Custom Dockerfile search
```
