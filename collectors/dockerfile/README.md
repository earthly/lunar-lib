# Dockerfile Collector

Parses Dockerfiles and collects container definition metadata including base images, final stage configuration, and labels.

## Overview

This collector finds all Dockerfiles in a repository and parses them using [dockerfile-json v1.2.2](https://github.com/keilerkonzept/dockerfile-json). It extracts structured information about container definitions including base images, user configuration, healthchecks, and labels. The collector runs on code changes and outputs normalized data for container-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.containers.source` | object | Tool metadata (tool name and version) |
| `.containers.definitions[]` | array | Parsed Dockerfile definitions with inline native AST |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dockerfile@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, containerized]
    # with:
    #   find_command: "find ./docker -name Dockerfile"  # Custom find command
```
