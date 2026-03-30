# .NET Project Guardrails

Enforce .NET-specific project standards including project file presence, target framework configuration, dependency locking, test project requirements, and minimum SDK version requirements for both development and CI/CD environments.

## Overview

This policy validates .NET projects against best practices for project structure and build configuration. It ensures projects have proper project files, specify target frameworks, use dependency locking for reproducible builds, include test projects for quality assurance, and meet minimum SDK version requirements for both development and CI/CD environments.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Severity | Failure Meaning |
|--------|-------------|----------|-----------------|
| `project-file-exists` | Validates .NET project file exists | Error | Project lacks buildable project file |
| `target-framework-set` | Ensures target framework is specified | Warning | Projects missing framework specification |
| `dependencies-locked` | Validates packages.lock.json exists | Warning | Dependencies not locked for reproducible builds |
| `test-project-exists` | Ensures at least one test project exists | Info | No automated tests detected |
| `min-sdk-version` | Ensures SDK version meets minimum requirements | Warning | Using outdated SDK version |
| `min-sdk-version-cicd` | Ensures CI/CD SDK version meets minimum requirements | Warning | CI/CD using outdated SDK version |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.dotnet` | object | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |
| `.lang.dotnet.project_files` | array | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |
| `.lang.dotnet.packages_lock_exists` | boolean | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |
| `.lang.dotnet.test_projects` | array | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |
| `.lang.dotnet.sdk_version` | string | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |
| `.lang.dotnet.cicd.cmds` | array | [`dotnet`](https://github.com/earthly/lunar-lib/tree/main/collectors/dotnet) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dotnet@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    enforcement: report-pr
    # include: [project-file-exists, target-framework-set]  # Only run specific checks
    # inputs:
    #   min_sdk_version: "8.0"        # Minimum SDK version for development
    #   min_sdk_version_cicd: "8.0"   # Minimum SDK version for CI/CD
```

## Examples

### Passing Example

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
          "target_framework": "net8.0"
        }
      ],
      "packages_lock_exists": true,
      "test_projects": [
        {
          "path": "MyApp.Tests/MyApp.Tests.csproj",
          "type": "csharp",
          "test_framework": "xunit"
        }
      ]
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "dotnet": {
      "project_files": [],
      "packages_lock_exists": false,
      "test_projects": []
    }
  }
}
```

**Failure messages:**
- `"No .NET project files found. Create a .csproj, .fsproj, or .vbproj file."`
- `"2 of 3 project(s) missing target framework: Add <TargetFramework>net8.0</TargetFramework> to project files."`
- `"No packages.lock.json found. Dependencies are not locked."`
- `"No test projects detected. Consider adding test projects."`

## Remediation

### project-file-exists
1. Create a new .NET project: `dotnet new console` (or `classlib`, `web`)
2. For F# projects: `dotnet new console -lang F#`
3. For existing code: Create a .csproj file manually or migrate from packages.config

### target-framework-set
1. Add `<TargetFramework>net8.0</TargetFramework>` to your .csproj files
2. Or for multi-targeting: `<TargetFrameworks>net6.0;net8.0</TargetFrameworks>`
3. Choose appropriate framework version for your deployment target

### dependencies-locked
1. Add `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>` to all project files
2. Run `dotnet restore` to generate packages.lock.json files
3. Commit all packages.lock.json files to version control
4. This ensures consistent dependency versions across environments

### test-project-exists
1. Create test projects:
   - `dotnet new xunit -n MyProject.Tests` (recommended)
   - `dotnet new nunit -n MyProject.Tests`
   - `dotnet new mstest -n MyProject.Tests`
2. Add project reference: `dotnet add MyProject.Tests reference MyProject.csproj`
3. Write unit tests and run with `dotnet test`

### min-sdk-version
1. Update global.json to specify minimum SDK version:
   ```json
   {
     "sdk": {
       "version": "8.0.100"
     }
   }
   ```
2. Install the required SDK version: `dotnet --install-sdk 8.0.100`
3. Verify installation: `dotnet --version`
4. Consider using `rollForward: "latestMinor"` policy for flexibility

### min-sdk-version-cicd
1. Update CI/CD pipeline files to use required SDK version:
   - **GitHub Actions**: Update `dotnet-version` in setup-dotnet action
   - **Azure DevOps**: Update `version` in DotNetCoreCLI task
   - **Jenkins**: Update SDK version in docker image or installation step
2. Example GitHub Actions update:
   ```yaml
   - uses: actions/setup-dotnet@v3
     with:
       dotnet-version: '8.0.x'
   ```
3. Test pipeline with updated SDK version before merging