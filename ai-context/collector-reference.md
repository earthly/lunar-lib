# Collector Reference

This document provides comprehensive documentation for writing Lunar collectors—the components that gather SDLC metadata and write it to the Component JSON.

## What is a Collector?

A **collector** is a script (Bash or Python) that:
1. Gathers information about a component (repository, CI artifacts, external APIs, etc.)
2. Writes that information to the Component JSON using the `lunar collect` command

Collectors run at specific trigger points (hooks) such as code changes, CI pipeline events, or scheduled times.

## Collector Definition

Collectors are defined in `lunar-config.yml` or as plugins in `lunar-collector.yml`.

### Inline Collector (in lunar-config.yml)

```yaml
collectors:
  # Run form - inline script
  - name: readme-check
    runBash: |
      if [ -f ./README.md ]; then
        lunar collect -j ".repo.readme_exists" true
      else
        lunar collect -j ".repo.readme_exists" false
      fi
    on: ["domain:my-domain"]
    hook:
      type: code

  # Main form - reference a script file
  - name: k8s-collector
    mainBash: ./collectors/k8s/main.sh
    on: [kubernetes]
    hook:
      type: code
```

### Plugin Collector (in lunar-collector.yml)

```yaml
version: 0

name: my-collector
description: Collects XYZ data from repositories
author: team@example.com

collectors:
  - name: my-collector
    description: Main collector logic
    mainBash: main.sh
    hook:
      type: code

inputs:
  threshold:
    description: Minimum threshold value
    default: "10"
```

**Usage in lunar-config.yml:**

```yaml
collectors:
  - uses: ./collectors/my-collector   # Local plugin
    on: ["domain:payments"]
    with:
      threshold: "20"

  - uses: github://acme/lunar-collectors@v1  # Remote plugin
    on: [backend]
```

### `include` and `exclude`

When importing a collector plugin that defines multiple subcollectors, selectively enable or disable specific ones:

```yaml
collectors:
  # Include only specific subcollectors
  - uses: ./collectors/go
    on: [go]
    include: [version, dependencies]  # Only run these two

  # Exclude specific subcollectors
  - uses: ./collectors/go
    on: [go]
    exclude: [build-info]  # Run all except "build-info"
```

If neither `include` nor `exclude` is specified, all subcollectors are included by default.

## Hook Types

Hooks define **when** a collector runs and **in what context**.

### Code Hook

Runs when new commits are pushed to the component's repository.

```yaml
hook:
  type: code
```

**Context:** Lunar Runner with a fresh clone of the repository at the commit being evaluated.

**Use cases:**
- Analyzing source code files (Dockerfiles, K8s manifests, Terraform, etc.)
- Checking for file existence (README, CODEOWNERS, etc.)
- Parsing configuration files

### Cron Hook

Runs on a schedule, independent of code changes.

```yaml
hook:
  type: cron
  schedule: "0 2 * * *"    # Daily at 2am UTC
  clone-code: true          # Optional: clone the repo (default: false)
```

**Context:** Lunar Runner, optionally with a clone of the repository.

**Use cases:**
- Querying external APIs (Jira, PagerDuty, security scanners)
- Periodic compliance checks
- Aggregating data from multiple sources

### CI Hooks

Run during CI pipeline execution, with access to the CI environment.

| Hook Type | Trigger Point | Pattern Matches |
|-----------|---------------|-----------------|
| `ci-before-job` | Before a CI job starts | Job name |
| `ci-after-job` | After a CI job completes | Job name |
| `ci-before-step` | Before a CI step runs | Step name |
| `ci-after-step` | After a CI step completes | Step name |
| `ci-before-command` | Before a command executes | Full command line |
| `ci-after-command` | After a command executes | Full command line |

```yaml
hook:
  type: ci-after-command
  pattern: ^docker.*build.*   # Regex pattern
```

**Context:** Inside the CI pipeline, with access to:
- Build artifacts
- Test results
- Environment variables
- The `LUNAR_CI_COMMAND` variable (for command hooks)

**Use cases:**
- Capturing test coverage after test runs
- Inspecting Docker build commands
- Collecting CI timing information
- Detecting specific tools being run

### Multiple Hooks

A single collector can have multiple hooks:

```yaml
collectors:
  - name: multi-hook-collector
    mainBash: main.sh
    on: [backend]
    hooks:
      - type: code
      - type: ci-after-command
        pattern: ^go test.*
```

### Hook Options

#### `runs_on`

Controls when the hook triggers:

```yaml
hook:
  type: code
  runs_on: [prs, default-branch]  # Default: runs on both
```

| Value | Meaning |
|-------|---------|
| `prs` | Run on pull requests |
| `default-branch` | Run on the default branch (main/master) |

Default is `[prs, default-branch]`. Use `runs_on: [prs]` to run only on PRs, or `runs_on: [default-branch]` to run only on the main branch.

## Environment Variables

Collectors have access to these environment variables:

### Component Context

| Variable | Description | Example |
|----------|-------------|---------|
| `LUNAR_COMPONENT_ID` | Full component identifier | `github.com/acme/api` |
| `LUNAR_COMPONENT_DOMAIN` | Domain the component belongs to | `payments.api` |
| `LUNAR_COMPONENT_OWNER` | Component owner email | `jane@example.com` |
| `LUNAR_COMPONENT_PR` | PR number (if in PR context) | `123` or empty |
| `LUNAR_COMPONENT_HEAD_BRANCH` | Head branch of PR (branch with changes) | `feature/add-auth` |
| `LUNAR_COMPONENT_BASE_BRANCH` | Base branch of PR (target branch) | `main` |
| `LUNAR_COMPONENT_GIT_SHA` | Git SHA being evaluated | `abc123...` |
| `LUNAR_COMPONENT_TAGS` | Component tags (JSON array) | `["go","backend"]` |
| `LUNAR_COMPONENT_META` | Component metadata (JSON) | `{"tier":"1"}` |

### Collector Context

| Variable | Description |
|----------|-------------|
| `LUNAR_COLLECTOR_NAME` | Name of the current collector |
| `LUNAR_COLLECTOR_CI_PIPELINE` | CI pipeline name (for CI hooks) |
| `LUNAR_PLUGIN_ROOT` | Root directory of the plugin (for plugins) |
| `LUNAR_BIN_DIR` | Directory for installed binaries |

### Hub Connection

| Variable | Description |
|----------|-------------|
| `LUNAR_HUB_HOST` | Lunar Hub hostname |
| `LUNAR_HUB_INSECURE` | Whether to skip SSL verification |

### Secrets

Secrets are passed as `LUNAR_SECRET_<NAME>`:

```bash
# Access a secret named "GH_TOKEN"
curl -H "Authorization: token $LUNAR_SECRET_GH_TOKEN" ...
```

### CI Hook-Specific

For `ci-before-job`, `ci-after-job`, `ci-before-step`, `ci-after-step`, `ci-before-command`, and `ci-after-command` hooks:

| Variable | Description |
|----------|-------------|
| `LUNAR_CI` | CI provider identifier (github, buildkite, ...) |
| `LUNAR_CI_PIPELINE_RUN_ID` | Unique identifier for the current pipeline run |
| `LUNAR_CI_PIPELINE_NAME` | Name of the pipeline (if available) |
| `LUNAR_CI_JOB_ID` | Job ID |
| `LUNAR_CI_JOB_NAME` | Job name (if available) |

For `ci-before-step`, `ci-after-step`, `ci-before-command`, and `ci-after-command` hooks:

| Variable | Description |
|----------|-------------|
| `LUNAR_CI_STEP_INDEX` | Step index (1-based) |
| `LUNAR_CI_STEP_NAME` | Step name (if available) |

For `ci-before-command` and `ci-after-command` hooks:

| Variable | Description |
|----------|-------------|
| `LUNAR_CI_COMMAND` | Command and arguments of the hooked command |

```bash
# For ci-after-command hook on "docker build -t myimage ."
# LUNAR_CI_COMMAND contains the full command line
echo "Hooked command: $LUNAR_CI_COMMAND"
```

## The lunar collect Command

The `lunar collect` command writes data to the Component JSON.

### Basic Syntax

```bash
lunar collect [options] <json-path> <value> [<json-path> <value> ...]
```

### Options

| Option | Description |
|--------|-------------|
| `-j`, `--json` | Interpret value as JSON (not raw string) |
| `--component <id>` | Specify component (default: from environment) |

### Examples

```bash
# Write a string value
lunar collect ".repo.language" "go"

# Write a boolean (use -j for JSON interpretation)
lunar collect -j ".repo.readme_exists" true

# Write a number
lunar collect -j ".coverage.percentage" 85.5

# Write multiple values at once
lunar collect -j \
  ".repo.readme_exists" true \
  ".repo.readme_num_lines" 150

# Write JSON object
lunar collect -j ".config" '{"timeout": 30, "retries": 3}'

# Write JSON array
lunar collect -j ".tags" '["api", "backend", "go"]'

# Pipe JSON from stdin (use - as value)
cat results.json | lunar collect -j ".test.results" -

# Build JSON with jq and pipe it
jq -n '{valid: true, lines: 100}' | lunar collect -j ".analysis" -
```

### Path Syntax

JSON paths use dot notation:

```bash
lunar collect -j ".foo.bar.baz" "value"
# Results in: {"foo": {"bar": {"baz": "value"}}}

lunar collect -j ".items[0].name" "first"
# Results in: {"items": [{"name": "first"}]}
```

### Array Concatenation

When collecting to the same array path multiple times (e.g., from multiple CI runs), Lunar automatically concatenates the arrays. This is useful for collecting data from multiple CI jobs or steps in an append-only manner.

```bash
# First collection
lunar collect -j ".builds" '[{"image": "app1"}]'

# Second collection (different CI job)
lunar collect -j ".builds" '[{"image": "app2"}]'

# Result: {"builds": [{"image": "app1"}, {"image": "app2"}]}
```

## Installing Dependencies

Collectors can install dependencies via `install.sh`:

### Basic install.sh

```bash
#!/bin/bash
set -e

# Download and install a binary
curl -L "https://example.com/tool.tar.gz" | tar xz
mv tool "$LUNAR_BIN_DIR/"
```

### Platform-Specific Installation

Use platform-specific scripts for cross-platform support:

```
my-collector/
├── install.sh              # Fallback
├── install-linux.sh        # Linux (any arch)
├── install-linux-amd64.sh  # Linux x86_64
├── install-linux-arm64.sh  # Linux ARM64
├── install-darwin.sh       # macOS (any arch)
└── install-darwin-arm64.sh # macOS ARM64 (Apple Silicon)
```

**Resolution order:** `install-<os>-<arch>.sh` → `install-<os>.sh` → `install.sh`

### Example: Cross-Platform Binary Installation

```bash
#!/bin/bash
set -e

OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Linux)  PLATFORM="linux" ;;
  Darwin) PLATFORM="darwin" ;;
  *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

case "$ARCH" in
  x86_64)       ARCHITECTURE="amd64" ;;
  arm64|aarch64) ARCHITECTURE="arm64" ;;
  *)            echo "Unsupported arch: $ARCH"; exit 1 ;;
esac

curl -L "https://example.com/tool-${PLATFORM}-${ARCHITECTURE}.tar.gz" | tar xz
mv tool "$LUNAR_BIN_DIR/"
```

## File Inclusion Configuration

Collectors that analyze files should expose configuration for which files to process. The approach depends on whether single or multiple files are expected.

### Pattern A: Multiple Files Expected (find command)

When a collector processes multiple files of a certain type (e.g., all Dockerfiles, all YAML files), expose a `find_command` input that allows users to customize file discovery.

**lunar-collector.yml:**
```yaml
inputs:
  find_command:
    description: Command to find files (must output one file path per line)
    default: "find . -type f \\( -name Dockerfile -o -name '*.Dockerfile' -o -name 'Dockerfile.*' \\)"
```

**Why a find command?** This gives users full flexibility to:
- Filter by directory: `find ./k8s -type f -name '*.yaml'`
- Exclude paths: `find . -type f -name '*.yaml' ! -path './vendor/*'`
- Use alternative tools: `git ls-files '*.yaml'` (respects .gitignore)

### Pattern B: Single File with Multiple Possible Names (ordered path list)

When a collector expects exactly one file but it may have different possible names (e.g., README.md, README.txt, readme.md), expose a comma-separated list of candidate paths. The collector tries each path in order and uses the first one found.

**lunar-collector.yml:**
```yaml
inputs:
  paths:
    description: Comma-separated list of paths to try (first match wins)
    default: "README.md,README.txt,README,readme.md,readme.txt"
```

**Why ordered paths?** This pattern:
- Supports naming conventions (README.md vs README.rst)
- Allows priority (prefer README.md over readme.txt)
- Handles case sensitivity differences across filesystems
- Is simpler than a find command for the single-file case

### Choosing Between Patterns

| Scenario | Pattern | Input Name |
|----------|---------|------------|
| All Dockerfiles in repo | find command | `find_command` |
| All K8s manifests | find command | `find_command` |
| All Terraform files | find command | `find_command` |
| The README file | ordered paths | `paths` |
| The CODEOWNERS file | ordered paths | `paths` |
| Main config file | ordered paths | `paths` |

## Common Patterns

### Pattern 1: File Analysis

Analyze files in the repository and collect structured data.

```bash
#!/bin/bash
set -e

# Find and process files
find . -name '*.yaml' -type f | while read -r file; do
  # Parse and validate
  if yq -e '.' "$file" > /dev/null 2>&1; then
    echo "{\"path\": \"$file\", \"valid\": true}"
  else
    echo "{\"path\": \"$file\", \"valid\": false}"
  fi
done | jq -s '.' | lunar collect -j ".yaml_files" -
```

### Pattern 2: External API Query

Query external APIs and collect results.

```bash
#!/bin/bash
set -e

# Use secrets for authentication
RESPONSE=$(curl -fsS \
  -H "Authorization: Bearer $LUNAR_SECRET_API_TOKEN" \
  "https://api.example.com/repos/$LUNAR_COMPONENT_ID/status")

echo "$RESPONSE" | lunar collect -j ".external.status" -
```

### Pattern 3: CI Artifact Collection

Collect data from CI artifacts after a command runs.

```bash
#!/bin/bash
set -e

# This runs after "go test" via ci-after-command hook
if [ -f coverage.out ]; then
  COVERAGE=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | tr -d '%')
  lunar collect -j ".testing.coverage.percentage" "$COVERAGE"
fi
```

### Pattern 4: Conditional Collection Based on Context

Handle PR vs main branch differently.

```bash
#!/bin/bash
set -e

if [ -n "$LUNAR_COMPONENT_PR" ]; then
  # We're in a PR context
  echo "Running PR-specific collection..."
  lunar collect -j ".context.is_pr" true
else
  # We're on the main branch
  echo "Running main branch collection..."
  lunar collect -j ".context.is_pr" false
fi
```

### Pattern 5: Parallel Processing

Process many files efficiently.

```bash
#!/bin/bash
set -e

process_file() {
  local f="$1"
  # ... processing logic ...
  echo "{\"path\": \"$f\", \"result\": ...}"
}
export -f process_file

# Process files in parallel
find . -name '*.tf' -type f | \
  parallel -j 4 process_file | \
  jq -s '{files: .}' | \
  lunar collect -j ".terraform" -
```

### Pattern 6: Graceful Degradation

Handle missing data or errors gracefully.

```bash
#!/bin/bash
set -e

# Check for required tools/files
if ! command -v yq &> /dev/null; then
  echo "yq not installed, skipping collection"
  exit 0
fi

if [ ! -f config.yaml ]; then
  lunar collect -j ".config.exists" false
  exit 0
fi

# Proceed with collection
lunar collect -j ".config.exists" true
# ... more collection ...
```

## Plugin Structure

```
my-collector/
├── lunar-collector.yml    # Required: Plugin configuration
├── main.sh                # Main collector script
├── Dockerfile             # For non-CI collectors with additional dependencies
├── helper.sh              # Optional: Helper scripts
└── requirements.txt       # Optional: Python dependencies (baked into image)
```

### lunar-collector.yml Reference

```yaml
version: 0

name: my-collector                    # Required: Unique name
description: What this collector does # Optional
author: team@example.com              # Required

# Recommended: specify container image
default_image: earthly/lunar-scripts:1.0.0
default_image_ci_collectors: native  # CI collectors often need access to CI environment

collectors:
  - name: main-collector              # Can define multiple collectors
    description: Primary collection
    mainBash: main.sh                 # Or: runBash: "inline script"
    hook:
      type: code                      # Or: cron, ci-before-command, etc.

inputs:                               # Optional: Configurable inputs
  api_url:
    description: Base URL for API
    default: "https://api.example.com"
  threshold:
    description: Minimum threshold
    # No default = required input
```

## Container Images

Lunar runs collectors inside Docker containers, providing isolation and reproducibility.

**Recommendation:** Use the official `earthly/lunar-scripts:1.0.0` image (or a custom image that inherits from it) for collectors. The exception is **CI collectors**, which often need to run natively to access the CI environment directly.

### Image Resolution Order

The image used to run a collector is determined in this order (first match wins):

1. **Collector-level `image`** — Set directly on the collector in `lunar-config.yml`
2. **Plugin-level default** — Set in `lunar-collector.yml`
3. **Global default** — `default_image_ci_collectors` or `default_image_non_ci_collectors` in `lunar-config.yml`
4. **Global `default_image`** — Fallback in `lunar-config.yml`
5. **Implicit default** — `native` (no container)

### Global Default Images

Configure default images in `lunar-config.yml`:

```yaml
version: 0

default_image: earthly/lunar-scripts:1.0.0    # Recommended: use for all scripts
default_image_ci_collectors: native           # CI collectors often need CI environment access

# ... rest of configuration
```

### The `native` Value

The special value `native` explicitly opts out of containerized execution. The script runs directly on the host system.

**Use `native` only for CI collectors** that need direct access to the CI environment (environment variables, build artifacts, CI tools):

```yaml
collectors:
  - runBash: lunar collect .ci-info "$CI_JOB_ID"
    image: native  # CI collector needs access to CI environment
    hook:
      type: ci-after-command
      pattern: ^.*
    on: [my-tag]
```

**Do not use `native` for code or cron collectors.** These should always run in containers for consistency and isolation.

### Official Image: `earthly/lunar-scripts`

Lunar provides an official Docker image that includes:

- Alpine Linux (or `-debian` variant if needed for certain tools)
- Python 3 with venv
- Bash
- The `lunar` CLI
- Common tools: `jq`, `yq`, `curl`, `parallel`, `wget`

**For development**, the image automatically executes any `requirements.txt` and/or `install.sh` files found in the plugin directory.

**For production**, bake all dependencies directly into your image.

### Creating a Custom Image

When your collector requires additional dependencies (tools, binaries, Python packages), create a `Dockerfile` that inherits from the official base image:

```dockerfile
FROM earthly/lunar-scripts:1.0.0

# Install additional system dependencies (if needed)
RUN apk add --no-cache git make

# Or download binaries
ARG TARGETARCH=amd64
RUN curl -sSL "https://example.com/tool-${TARGETARCH}.tar.gz" | tar xz && \
    mv tool /usr/local/bin/
```

### Building and Publishing the Image

Build and push the image to your container registry:

```bash
docker build -t your-registry/my-collector:1.0.0 ./collectors/my-collector
docker push your-registry/my-collector:1.0.0
```

Then reference this image in your `lunar-collector.yml`:

```yaml
default_image: your-registry/my-collector:1.0.0
```

**Important:** Always bake dependencies into the image rather than using `install.sh` for production. This provides faster startup, reproducible builds, and eliminates network dependencies at runtime.

### Accessing Inputs

Inputs are passed as environment variables with the input name in uppercase:

```bash
#!/bin/bash
# If input is named "api_url", access it as:
echo "API URL: $API_URL"
echo "Threshold: $THRESHOLD"
```

## Best Practices

### 1. Always Use `set -e`

Exit on first error to avoid partial/incorrect data.

```bash
#!/bin/bash
set -e
```

### 2. Handle Missing Data Gracefully

Don't fail if optional files/tools are missing.

```bash
if [ -f optional-file.json ]; then
  # collect data
fi
```

### 3. Use Structured JSON

Prefer structured objects over flat values.

```bash
# Good - structured object with related data grouped together
lunar collect -j ".containers.definitions[0]" '{"path": "Dockerfile", "valid": true, "base_images": [{"reference": "node:18-alpine"}]}'

# Less good - flat values scattered at different paths
lunar collect -j ".dockerfile_exists" true
lunar collect -j ".dockerfile_base_images" '["node:18"]'
```

See [component-json-conventions.md](component-json-conventions.md) for design principles and conventions, and [component-json-structure.md](component-json-structure.md) for the standard category structures.

### 4. Include Context in Collected Data

Include file paths, timestamps, or other context.

```bash
jq -n \
  --arg path "$FILE" \
  --arg sha "$LUNAR_COMPONENT_GIT_SHA" \
  '{path: $path, git_sha: $sha, valid: true}' | \
  lunar collect -j ".analysis" -
```

### 5. Keep Collectors Focused

One collector should collect one type of data. Create separate collectors for different concerns.

### 6. Test Locally

Use `lunar collect --component <id>` to test collectors locally:

```bash
LUNAR_COMPONENT_ID="github.com/acme/api" ./main.sh
```

### 7. Document Component JSON Schema

Document what paths your collector writes to, so policy authors know what to expect.
