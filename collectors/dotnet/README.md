# .NET Collector

Collects .NET/C# project information, dependencies, and test project detection.

## Overview

This collector gathers metadata about .NET projects including project structure detection, target frameworks, NuGet dependencies, project references, and test project identification. It supports C#, F#, and VB.NET projects with both SDK-style and legacy project formats. Code hooks analyze project files statically to extract build and dependency information.

**Note:** This collector analyzes project files at rest—it doesn't build or run projects, just reads their configuration.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.dotnet` | object | .NET project metadata (SDK version, frameworks, project files, test projects) |
| `.lang.dotnet.dependencies` | object | NuGet packages and project references from project files |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Detects .NET project structure, target frameworks, SDK versions, test projects |
| `dependencies` | code | Extracts NuGet dependencies and project references from project files |

## Detection Logic

The collector identifies .NET projects by looking for these indicators (up to 3 directories deep):

- **Project files**: `*.csproj`, `*.fsproj`, `*.vbproj`
- **Solution files**: `*.sln`
- **SDK configuration**: `global.json`
- **Build configuration**: `Directory.Build.props`
- **Dependency locking**: `packages.lock.json`

If none of these files are found, the collector returns empty JSON (skip-safe behavior).

## Project Analysis

For each project file found, the collector extracts:

- **Target framework(s)**: From `<TargetFramework>` or `<TargetFrameworks>`
- **Project type**: Inferred from `<OutputType>`, SDK type, or package references
- **Output type**: `console`, `library`, `web`, `test`, or `windows`
- **Language**: `csharp`, `fsharp`, or `vb.net` based on file extension
- **Test framework**: `xunit`, `nunit`, `mstest` based on package references

## Test Project Detection

Projects are identified as test projects when:

- They reference test framework packages (`Microsoft.NET.Test.Sdk`, `xunit`, `NUnit`, `MSTest.TestFramework`)
- Their path contains test-related keywords (`test`, `tests`, `spec`, `specs`)
- They use test-specific SDK types

## Dependencies

The collector extracts:

- **NuGet packages**: From `<PackageReference>` elements with name and version
- **Project references**: From `<ProjectReference>` elements with relative paths

Duplicate dependencies are automatically deduplicated across multiple project files.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dotnet@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```

## Example Output

```json
{
  "lang": {
    "dotnet": {
      "sdk_version": "8.0.100",
      "target_frameworks": ["net8.0"],
      "project_files": [
        {
          "path": "MyApp/MyApp.csproj",
          "type": "csharp",
          "output_type": "console",
          "target_framework": "net8.0"
        }
      ],
      "solution_files": ["MyApp.sln"],
      "global_json_exists": true,
      "directory_build_props_exists": false,
      "packages_lock_exists": true,
      "test_projects": [
        {
          "path": "MyApp.Tests/MyApp.Tests.csproj",
          "type": "csharp",
          "test_framework": "xunit"
        }
      ],
      "source": { "tool": "dotnet", "integration": "code" },
      "dependencies": {
        "direct": [
          {
            "name": "Microsoft.Extensions.Hosting",
            "version": "8.0.0",
            "type": "package"
          }
        ],
        "project_references": [
          {
            "path": "MyLibrary/MyLibrary.csproj"
          }
        ],
        "source": { "tool": "dotnet", "integration": "code" }
      }
    }
  }
}
```