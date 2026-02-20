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

| Hook Type | Trigger Point | Matching |
|-----------|---------------|----------|
| `ci-before-job` | Before a CI job starts | Job name regex |
| `ci-after-job` | After a CI job completes | Job name regex |
| `ci-before-step` | Before a CI step runs | Step name regex |
| `ci-after-step` | After a CI step completes | Step name regex |
| `ci-before-command` | Before a command executes | Structured binary/args/envs matching |
| `ci-after-command` | After a command executes | Structured binary/args/envs matching |

#### Job and Step Hooks

Job and step hooks use a `pattern` field to match job or step names by regex:

```yaml
hook:
  type: ci-after-job
  pattern: ^build$         # Regex matching the job name
```

If no pattern is specified, the hook triggers on every job/step.

#### Command Hooks

Command hooks (`ci-before-command` / `ci-after-command`) use **structured matching** to target specific commands. This is more precise and less error-prone than regex matching against the full command line.

**Simple form** — match by binary name and positional/flag arguments:

```yaml
hook:
  type: ci-after-command
  binary:
    name: docker
  args:
    - value: build
```

**Advanced form** — add regex patterns, environment variable matchers, and process depth control:

```yaml
hook:
  type: ci-after-command
  binary:
    name_pattern: python[0-9]*    # Regex on binary name
    dir: /usr/local/bin            # Exact dir match (or dir_pattern for regex)
    use_path_dirs: true            # Restrict to PATH directories
  args:
    - value: build                 # Positional arg (order matters)
    - flag: --tag                  # Flag (order-independent)
      value_pattern: ^v[0-9]+      # Regex on flag value
  args_pattern: .*--verbose.*     # Regex on full args string (alternative/complement to args array)
  envs:
    - name: DEBUG
      value: "1"
  max_process_depth: 1             # Only top-level processes
  include_children_depth: 1        # Also trigger on direct children
```

**Matching rules:**
- All specified matchers (`binary`, `args`, `envs`) must match (AND logic)
- For OR logic, use regex alternation (e.g., `flag_pattern: ^(-f|--file)$`)
- `name` vs `name_pattern`: exact match vs regex (mutually exclusive); same for `dir`/`dir_pattern`, `flag`/`flag_pattern`, `value`/`value_pattern`
- `args` positional matchers (value-only, no flag) must appear in order; flag matchers can be in any order
- A flag matcher with no `value`/`value_pattern` matches boolean flags (flags that take no value)

> **Deprecated:** The old `pattern: <regex>` form for command hooks (regex against the full command line) is deprecated. Use the structured `binary`/`args` form instead.

**Common examples:**

```yaml
# Match "go test" commands
hook:
  type: ci-after-command
  binary:
    name: go
  args:
    - value: test

# Match "docker build" with any tag
hook:
  type: ci-after-command
  binary:
    name: docker
  args:
    - value: build
    - flag_pattern: ^(-t|--tag)$
      value_pattern: .*

# Match "npm run", "npm test", or "npm build"
hook:
  type: ci-after-command
  binary:
    name: npm
  args:
    - value_pattern: ^(run|test|build)$

# Match any command (all processes in CI)
hook:
  type: ci-after-command
```

**Context:** Inside the CI pipeline, with access to:
- Build artifacts
- Test results
- Environment variables
- The `LUNAR_CI_COMMAND` variable (JSON array of the command and its arguments)

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
        binary:
          name: go
        args:
          - value: test
```

### `runs_on`

Controls when the collector triggers:

```yaml
collectors:
  - name: my-collector
    mainBash: main.sh
    runs_on: [prs, default-branch]  # Default: runs on both
    hook:
      type: code
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
| `LUNAR_CI_COMMAND` | Command and arguments of the hooked command (JSON array of strings, e.g., `["go","test","./..."]`) |

```bash
# For ci-after-command hook on "docker build -t myimage ."
# LUNAR_CI_COMMAND is a JSON array: ["docker","build","-t","myimage","."]

# Container-based collectors can use jq (available in official image):
echo "Hooked command: $(echo "$LUNAR_CI_COMMAND" | jq -r 'join(" ")')"

# Native collectors should use pure bash (no jq dependency):
CMD_STR=$(echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
echo "Hooked command: $CMD_STR"
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

**Prefer containers.** Non-CI collectors should bake dependencies into a Docker image via `default_image` (see [Container Images](#container-images)). This eliminates installation concerns entirely.

For native CI collectors, prefer tools already present in CI environments (`curl`, `git`, `bash` builtins) and avoid installing binaries when possible. When a specialized tool is genuinely required, provide a minimal `install.sh`:

```bash
#!/bin/bash
set -e
curl -L "https://example.com/tool.tar.gz" | tar xz
mv tool "$LUNAR_BIN_DIR/"
```

Platform-specific variants are supported: `install-<os>-<arch>.sh` → `install-<os>.sh` → `install.sh`.

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

### Pattern B: Single Item with Multiple Candidate Paths (ordered path list)

When a collector expects exactly one file or directory but it may exist at different paths, expose a comma-separated list of candidate paths. The collector tries each path in order and uses the first one found.

**lunar-collector.yml:**
```yaml
inputs:
  # For a file with multiple possible names
  paths:
    description: Comma-separated list of paths to try (first match wins)
    default: "README.md,README.txt,README,readme.md,readme.txt"

  # For a directory with multiple possible locations
  plans_dir_paths:
    description: Comma-separated list of candidate directory paths (first match wins)
    default: ".agents/plans,.ai/plans"
```

**Why ordered paths?** This pattern:
- Supports naming conventions (README.md vs README.rst, `.agents/plans` vs `.ai/plans`)
- Allows priority (prefer README.md over readme.txt)
- Handles case sensitivity differences across filesystems
- Is simpler than a find command for the single-item case
- Works for both files and directories

### Choosing Between Patterns

| Scenario | Pattern | Input Name |
|----------|---------|------------|
| All Dockerfiles in repo | find command | `find_command` |
| All K8s manifests | find command | `find_command` |
| All Terraform files | find command | `find_command` |
| All AGENTS.md/CLAUDE.md files | find command | `find_command` |
| The README file | ordered paths | `paths` |
| The CODEOWNERS file | ordered paths | `paths` |
| Main config file | ordered paths | `paths` |
| Plans directory | ordered paths | `paths` |

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
# Hook config: binary.name: go, args: [{value: test}]
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
├── helpers.sh             # Optional: Shared helper functions
└── requirements.txt       # Optional: Python dependencies (baked into image)
```

### lunar-collector.yml Reference

```yaml
version: 0

name: my-collector                    # Required: Unique name (must match directory name)
description: What this collector does # Required: Brief description
author: team@example.com              # Required

# Recommended: specify container image
# Use default_image alone when plugin has no CI collectors
# Add default_image_ci_collectors: native when plugin includes CI collectors
default_image: earthly/lunar-scripts:1.0.0

# === Landing page metadata (required for public plugins) ===
landing_page:
  display_name: "My Collector"        # Required: Max 50 chars, must end with "Collector"
  long_description: |                 # Required: Max 300 chars, used for hero tagline + meta description
    Collects XYZ data from repositories. Enables enforcement of 
    ABC standards across your organization.
  category: "devex-build-and-ci"      # Required: See categories below
  status: "stable"                    # Required: stable|beta|experimental|deprecated
  icon: "assets/my-icon.svg"          # Required: Path relative to plugin directory
  
  # Related plugins for cross-linking (optional)
  related:
    - slug: "my-policy"               # Plugin directory name
      type: "policy"                  # collector|policy|cataloger
      reason: "Enforces standards using this collector's data"  # Max 80 chars

# === Collectors (sub-components) ===
collectors:
  - name: main-collector              # Required: Unique within plugin
    description: |                    # Required: Multi-line description for landing page
      Collects XYZ data including:    # Describe WHAT is collected, not HOW.
      - Feature A                     # Don't mention Component JSON paths or
      - Feature B                     # implementation details.
    mainBash: main.sh                 # Or: runBash: "inline script"
    hook:
      type: code                      # Or: cron, ci-before-command, etc.
    keywords: ["keyword1", "keyword2", "seo term"]  # Required: SEO keywords

# === Inputs (optional) ===
inputs:
  api_url:
    description: Base URL for API
    default: "https://api.example.com"
  threshold:
    description: Minimum threshold
    # No default = required input

# === Secrets (optional) ===
secrets:
  - name: API_TOKEN
    description: API authentication token
    required: true

# === Example output (required for public plugins) ===
example_component_json: |
  {
    "my_category": {
      "items": [
        {"name": "example", "valid": true}
      ]
    }
  }
```

### Landing Page Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `landing_page.display_name` | Yes | Human-readable name, max 50 chars, must end with "Collector" |
| `landing_page.long_description` | Yes | Marketing description, max 300 chars, used for hero + meta |
| `landing_page.category` | Yes | One of the 6 valid categories (see below) |
| `landing_page.status` | Yes | `stable`, `beta`, `experimental`, or `deprecated` |
| `landing_page.icon` | Yes | Path to SVG icon relative to plugin directory (file must exist) |
| `landing_page.related[]` | No | Array of related plugins (`slug`, `type`, `reason` max 80 chars) |
| `collectors[].keywords` | Yes | Array of SEO keywords for this sub-collector (at least 1) |
| `secrets[]` | No | Array of secrets this collector needs (for website display) |
| `example_component_json` | No | Example JSON output (for website display, recommended) |

**Cross-validation:** The README title (`# ...`) must match `landing_page.display_name` exactly.

**Note:** `landing_page.requires` is not allowed for collectors (only for policies).

### Categories

| Slug | Display Name |
|------|--------------|
| `repository-and-ownership` | Repository & Ownership |
| `deployment-and-infrastructure` | Deployment & Infrastructure |
| `testing-and-quality` | Testing & Quality |
| `devex-build-and-ci` | DevEx, Build & CI |
| `security-and-compliance` | Security & Compliance |
| `operational-readiness` | Operational Readiness |

### Status Values

| Status | Description |
|--------|-------------|
| `stable` | Production ready, well tested |
| `beta` | Feature complete, API stable |
| `experimental` | Early development, API may change |
| `deprecated` | No longer recommended |

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

default_image: earthly/lunar-scripts:1.0.0    # Used for all collectors by default
default_image_ci_collectors: native           # Only add when you have CI collectors

# ... rest of configuration
```

**Convention:**
- Use `default_image` alone when your plugin has no CI collectors
- Add `default_image_ci_collectors: native` only when your plugin includes CI collectors (hooks like `ci-after-command`, `ci-after-job`, etc.)

### The `native` Value

The special value `native` explicitly opts out of containerized execution. The script runs directly on the host system.

**Use `native` only for CI collectors** that need direct access to the CI environment (environment variables, build artifacts, CI tools):

```yaml
collectors:
  - runBash: lunar collect .ci-info "$CI_JOB_ID"
    image: native  # CI collector needs access to CI environment
    hook:
      type: ci-after-command  # No binary/args = matches all commands
    on: [my-tag]
```

**Do not use `native` for code or cron collectors.** These should always run in containers for consistency and isolation.

**Writing CI collectors for maximum compatibility:** When writing CI collectors (especially those marked `native`), keep scripts as native-bash as possible. Avoid dependencies like `jq`, `yq`, or other tools that may not be present in all CI environments. If dependencies are absolutely necessary, they can be installed via an `install.sh` script, but this adds overhead and reduces compatibility. The goal is to run reliably across GitHub Actions, GitLab CI, CircleCI, BuildKite, and other CI providers without assumptions about the environment.

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

Inputs are passed as environment variables with the prefix `LUNAR_VAR_` and the input name in uppercase:

```bash
#!/bin/bash
# If input is named "api_url", access it as:
echo "API URL: $LUNAR_VAR_API_URL"
```

### Shared Helper Functions

When multiple scripts in a collector share common logic, extract it into `helpers.sh` and source it:

```bash
source "$(dirname "$0")/helpers.sh"
```

The `$(dirname "$0")` pattern ensures the path resolves relative to the script's location, not the current working directory.

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

Use `lunar collector dev` to test collectors in development mode. Run from your config directory (where `lunar-config.yml` lives).

```bash
# Run all subcollectors in a plugin against a local repo
lunar collector dev <plugin-name> --component-dir <path> --verbose

# Run a specific subcollector
lunar collector dev <plugin-name>.<subcollector> --component-dir <path> --verbose

# Run against a remote component (fetches from GitHub)
lunar collector dev <plugin-name> --component github.com/org/repo --verbose

# Test CI hooks by simulating a CI command
lunar collector dev <plugin-name> --component-dir <path> --fake-ci-cmd "go test ./..."

# Pipe output into a policy for end-to-end testing
lunar collector dev <plugin-name> --component-dir <path> | \
  lunar policy dev <policy-name> --component-json - --verbose
```

| Flag | Description |
|------|-------------|
| `--component-dir <path>` | Local repo directory (mutually exclusive with `--component`) |
| `--component <id>` | Remote component (e.g. `github.com/org/repo`) |
| `--verbose` | Show detailed execution output |
| `--fake-ci-cmd <cmd>` | Simulate a CI command for testing CI hooks |
| `--pr <num>` | Simulate PR context |
| `--git-sha <sha>` | Run against a specific commit |
| `--merge` | Merge all diffs into a single JSON blob (default: true) |

**Note:** The name argument uses prefix matching — `my-plugin` runs all subcollectors named `my-plugin.*`.

### 7. Document Component JSON Schema

Document what paths your collector writes to, so policy authors know what to expect.

### 8. Naming Convention: `.cicd` vs `.auto` Sub-Keys for CI-Detected and Auto-Run Collectors

Many collectors either **detect a tool running in CI** or **auto-run a tool** themselves. Use consistent sub-key naming to distinguish how data was produced. See [Component JSON Conventions — CI Detection and Auto-Run Naming](component-json/conventions.md#ci-detection-and-auto-run-naming) for the full schema contract.

| Sub-key | Meaning | Hook type | Example path |
|---------|---------|-----------|--------------|
| `.cicd` | Tool was **detected running in CI** — records command invocations | `ci-after-command` / `ci-before-command` | `.lang.go.cicd`, `.containers.docker.cicd` |
| `.auto` | Tool was **auto-run by Lunar** — records execution results | `code` / `cron` | `.sast.semgrep.auto`, `.sbom.syft.auto` |
| *(neither)* | Normalized data from any source — tool-agnostic | any | `.sca.vulnerabilities`, `.testing.coverage` |

**Key rules:**

1. **`.cicd` collectors** should collect **all** invocations into a `cmds` array (not just the first match or a boolean). Each entry should include the command string and, where possible, the CLI version. Lunar [auto-concatenates arrays](#array-concatenation) at the same path, so each CI invocation appends to the list. This gives maximum visibility—policies can enforce minimum CLI versions, flag outdated tools, and detect version discrepancies across CI jobs.

2. **`.auto` collectors** should record execution metadata (exit code, version, pass/fail) and write results into both the tool-specific `.auto` sub-key and normalized category paths.

3. **Normalized paths** (e.g., `.sca.vulnerabilities`, `.testing.coverage`) remain tool-agnostic—any source can populate them.

See `collectors/golang/cicd.sh` for a reference implementation of the `.cicd` pattern.
