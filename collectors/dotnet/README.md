# .NET Collector

Collects .NET/C# project information, dependencies, and test project detection.

## Overview

This collector gathers metadata about .NET projects including project structure detection, target frameworks, NuGet dependencies, project references, and test project identification. It supports C#, F#, and VB.NET projects with both SDK-style and legacy project formats. Code hooks analyze project files statically to extract build and dependency information.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.dotnet` | object | .NET project metadata (SDK version, frameworks, project files, test projects) |
| `.lang.dotnet.dependencies` | object | NuGet packages and project references from project files |
| `.lang.dotnet.cicd` | object | CI/CD command tracking with SDK version |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects .NET project structure, target frameworks, SDK versions, test projects |
| `dependencies` | code | Extracts NuGet dependencies and project references from project files |
| `cicd` | ci-before-command | Tracks dotnet commands in CI with SDK version |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dotnet@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```