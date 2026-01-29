# Cataloger Reference

This document provides comprehensive documentation for writing Lunar catalogers—the components that synchronize software catalog information (domains and components) with external systems.

## What is a Cataloger?

A **cataloger** is a script (Bash) that:
1. Fetches information about domains and components from external sources (APIs, databases, files, etc.)
2. Writes that information to the Catalog JSON using the `lunar catalog` command

Catalogers define the organizational structure of your software portfolio—what components exist, who owns them, which domain they belong to, and their metadata.

## Catalogers vs Collectors

| Aspect | Cataloger | Collector |
|--------|-----------|-----------|
| **Purpose** | Define *what* components/domains exist | Gather *data about* components |
| **Output** | Catalog JSON (domains, components, metadata) | Component JSON (SDLC data) |
| **Scope** | Organization-wide catalog | Per-component data |
| **Trigger** | Cron schedule, repo commits | Code changes, CI events |
| **Command** | `lunar catalog` | `lunar collect` |

## Cataloger Definition

Catalogers are defined in `lunar-config.yml` or as plugins in `lunar-cataloger.yml`.

### Inline Cataloger (in lunar-config.yml or lunar-cataloger.yml)

```yaml
catalogers:
  # Run form - inline script
  - name: github-repos
    runBash: |
      gh repo list my-org --json name,owner | \
        jq '[.[] | {(.name): {owner: .owner.login}}]' | \
        lunar catalog --json '.components' -
    hook:
      type: cron
      schedule: "0 2 * * *"

  # Main form - reference a script file
  - name: backstage-sync
    mainBash: ./catalogers/backstage/main.sh
    hook:
      type: cron
      schedule: "0 3 * * *"
```

### Plugin Cataloger (in lunar-cataloger.yml)

```yaml
version: 0

name: my-cataloger
description: Syncs catalog from external system
author: team@example.com

default_image: earthly/lunar-scripts:1.0.0

catalogers:
  - name: sync-components
    description: Fetches component list from API
    mainBash: main.sh
    hook:
      type: cron
      schedule: "0 2 * * *"

inputs:
  api_url:
    description: Base URL for the catalog API
    default: "https://api.example.com"
  org_name:
    description: Organization name to sync
    # No default = required input
```

**Usage in lunar-config.yml:**

```yaml
catalogers:
  - uses: ./catalogers/my-cataloger   # Local plugin
    with:
      org_name: "acme-corp"

  - uses: github://acme/lunar-catalogers@v1  # Remote plugin
```

### `include` and `exclude`

When importing a cataloger plugin that defines multiple sub-catalogers, selectively enable or disable specific ones:

```yaml
catalogers:
  # Include only specific sub-catalogers
  - uses: ./catalogers/backstage
    include: [components]  # Only sync components

  # Exclude specific sub-catalogers
  - uses: ./catalogers/backstage
    exclude: [users]  # Sync all except users

  # Include components and domains only
  - uses: ./catalogers/backstage
    include: [components, domains]
```

If neither `include` nor `exclude` is specified, all sub-catalogers are included by default.

## Hook Types

Hooks define **when** a cataloger runs and **in what context**.

### Cron Hook

Runs on a schedule, independent of code changes.

```yaml
hook:
  type: cron
  schedule: "0 2 * * *"    # Daily at 2am UTC
```

**Context:** Lunar Runner, no repository clone.

**Use cases:**
- Syncing from external APIs (Backstage, ServiceNow, custom CMDBs)
- Periodic database queries
- Aggregating data from multiple sources

### Repo Hook

Runs when commits are made to a specific repository.

```yaml
hook:
  type: repo
  repo: github.com/acme/software-catalog
```

**Context:** Lunar Runner with a clone of the specified repository.

**Use cases:**
- Reading catalog definitions from a central repository
- Processing TOML/YAML/JSON files that define components
- Syncing from GitOps-style catalog repos

### Component-Repo Hook

Runs when commits are made to any component repository.

```yaml
hook:
  type: component-repo
```

**Context:** Lunar Runner with a clone of the component's repository.

**Use cases:**
- Augmenting component metadata from repo contents
- Reading ownership from files like `CODEOWNERS` or `lunar.yml`
- Inferring tags from repository structure

**Note:** This hook cannot create new components—only augment existing ones.

## Environment Variables

Catalogers have access to these environment variables:

### Hub Connection

| Variable | Description |
|----------|-------------|
| `LUNAR_HUB_HOST` | Lunar Hub hostname |
| `LUNAR_HUB_INSECURE` | Whether to skip SSL verification |

### Cataloger Context

| Variable | Description |
|----------|-------------|
| `LUNAR_CATALOGER_NAME` | Name of the current cataloger |
| `LUNAR_CATALOGER_OWNER` | Owner of the cataloger |
| `LUNAR_BIN_DIR` | Directory for installed binaries |
| `LUNAR_PLUGIN_ROOT` | Root directory of the plugin (for plugins) |

### Secrets

Secrets are passed as `LUNAR_SECRET_<NAME>`:

```bash
# Access a secret named "BACKSTAGE_TOKEN"
curl -H "Authorization: Bearer $LUNAR_SECRET_BACKSTAGE_TOKEN" ...
```

### Component-Repo Hook Context

For `component-repo` hooks only:

| Variable | Description |
|----------|-------------|
| `LUNAR_COMPONENT_ID` | Component identifier being processed |

## The lunar catalog Command

The `lunar catalog` command writes data to the Catalog JSON.

### Forms

#### Raw Form

Write arbitrary JSON to any path in the Catalog JSON.

```bash
lunar catalog raw [--json] <json-path> <value>
```

**Examples:**

```bash
# Write components to the catalog
lunar catalog --json '.components' '{"github.com/acme/api": {"owner": "jane@acme.com"}}'

# Pipe JSON from command output
gh repo list my-org --json name,owner | jq '...' | lunar catalog --json '.components' -

# Write domains
lunar catalog --json '.domains' '{"platform": {"owner": "platform-team@acme.com"}}'
```

#### Component Form

Write or update a single component with structured flags.

```bash
lunar catalog component [options] [<json-value>]
```

| Flag | Description |
|------|-------------|
| `--name <n>` | Component name (required unless in component-repo hook) |
| `--owner <owner>` | Component owner email |
| `--branch <branch>` | Default branch name |
| `--domain <domain>` | Domain path (e.g., `platform.api`) |
| `--tag <tag>` | Add a tag (repeatable) |
| `--ci-pipeline <name>` | Add a CI pipeline (repeatable) |
| `--meta <key>=<value>` | Add metadata (string value, repeatable) |
| `--meta-json <key>=<value>` | Add metadata (JSON value, repeatable) |

**Examples:**

```bash
# Add component with flags
lunar catalog component \
  --name "github.com/acme/api" \
  --owner "jane@acme.com" \
  --domain "platform.backend" \
  --tag "go" \
  --tag "production"

# Add tag to current component (in component-repo hook)
lunar catalog component --tag production

# Set metadata
lunar catalog component \
  --name "github.com/acme/api" \
  --meta tier=1 \
  --meta-json slos='{"latency_p99": 100}'
```

#### Domain Form

Write or update a single domain.

```bash
lunar catalog domain [options] [<json-value>]
```

| Flag | Description |
|------|-------------|
| `--name <n>` | Domain name (required) |
| `--description <desc>` | Domain description |
| `--owner <owner>` | Domain owner email |
| `--meta <key>=<value>` | Add metadata (string value, repeatable) |
| `--meta-json <key>=<value>` | Add metadata (JSON value, repeatable) |

**Examples:**

```bash
# Create a domain
lunar catalog domain \
  --name "platform" \
  --description "Platform services" \
  --owner "platform-team@acme.com"

# Create nested domain
lunar catalog domain \
  --name "platform.backend" \
  --description "Backend platform services"
```

### Path Syntax

JSON paths use dot notation:

```bash
lunar catalog --json '.components["github.com/acme/api"]' '{"owner": "jane@acme.com"}'
# Results in: {"components": {"github.com/acme/api": {"owner": "jane@acme.com"}}}
```

### Reading from stdin

Use `-` as the value to read JSON from standard input:

```bash
cat components.json | lunar catalog --json '.components' -

curl -s https://api.example.com/services | \
  jq '[.services[] | {(.repo): {owner: .owner}}] | add' | \
  lunar catalog --json '.components' -
```

## Catalog JSON Structure

The Catalog JSON has a predefined structure:

```json
{
  "domains": {
    "<domain-name>": {
      "description": "<description>",
      "owner": "<owner>",
      "meta": {
        "<key>": "<value>"
      }
    }
  },
  "components": {
    "<component-name>": {
      "owner": "<owner>",
      "domain": "<domain>",
      "branch": "<branch>",
      "tags": ["<tag1>", "<tag2>"],
      "ciPipelines": ["<pipeline1>", "<pipeline2>"],
      "meta": {
        "<key>": "<value>"
      }
    }
  }
}
```

### Merge Precedence

Catalog information is merged from multiple sources. Later sources override earlier ones:

1. **Catalogers** (in definition order—later catalogers override earlier)
2. **`lunar.yml`** files in component repositories
3. **`lunar-config.yml`** `domains` and `components` sections (highest precedence)

## Common Patterns

### Pattern 1: External API Sync (cron hook)

Fetch component data from an external service catalog. Uses a `cron` hook to sync periodically.

```bash
#!/bin/bash
set -e

# Hook: type: cron, schedule: "0 2 * * *"

# Query Backstage API for all components
COMPONENTS=$(curl -fsS \
  -H "Authorization: Bearer $LUNAR_SECRET_BACKSTAGE_TOKEN" \
  "https://backstage.example.com/api/catalog/entities?filter=kind=component")

# Transform and write to catalog
echo "$COMPONENTS" | jq '
  [.[] | {
    (.metadata.annotations["github.com/repo"]): {
      owner: .spec.owner,
      domain: .spec.domain,
      tags: .metadata.tags
    }
  }] | add
' | lunar catalog --json '.components' -
```

### Pattern 2: Database Sync (cron hook)

Sync catalog from a database. Uses a `cron` hook to sync periodically.

```bash
#!/bin/bash
set -e

# Hook: type: cron, schedule: "0 2 * * *"

# Export services from database
psql "$LUNAR_SECRET_DB_URL" -t -A -c "
  SELECT json_agg(json_build_object(
    repo_url, json_build_object(
      'owner', owner_email,
      'domain', domain_path,
      'tags', ARRAY[tier, team]
    )
  ))
  FROM services
  WHERE active = true
" | lunar catalog --json '.components' -
```

### Pattern 3: Central Repository Files (repo hook)

Read catalog definitions from files in a central repo. Uses a `repo` hook to run when the catalog repo is updated.

```bash
#!/bin/bash
set -e

# Hook: type: repo, repo: github.com/acme/software-catalog

# Import domains from TOML file
cat domains.toml | toml2json | jq '.domains' | lunar catalog --json '.domains' -

# Import components from YAML file
cat services.yaml | yq -o=json '.components' | lunar catalog --json '.components' -
```

### Pattern 4: Component-Level Augmentation (component-repo hook)

Augment components from their own repos. Uses a `component-repo` hook to run on commits to any component repository.

```bash
#!/bin/bash
set -e

# Hook: type: component-repo

# Add tag if repo has a specific CI workflow
if grep -q '^name: Production Deploy$' .github/workflows/*.yml 2>/dev/null; then
  lunar catalog component --tag production
fi

# Add tag based on language detection
if [ -f go.mod ]; then
  lunar catalog component --tag go
elif [ -f package.json ]; then
  lunar catalog component --tag javascript
elif [ -f requirements.txt ] || [ -f pyproject.toml ]; then
  lunar catalog component --tag python
fi
```

### Pattern 5: GitHub Organization Sync (cron hook)

Sync all repos from a GitHub organization. Uses a `cron` hook to sync periodically.

```bash
#!/bin/bash
set -e

# Hook: type: cron, schedule: "0 2 * * *"

# List all repos and transform to catalog format
gh repo list my-org --json name,owner,description,url \
  --limit 1000 | jq '
  [.[] | {
    (.url | gsub("https://"; "")): {
      owner: .owner.login,
      meta: {description: .description}
    }
  }] | add
' | lunar catalog --json '.components' -
```

### Pattern 6: Multi-Source Aggregation (cron hook)

Combine data from multiple sources. Uses a `cron` hook to sync periodically.

```bash
#!/bin/bash
set -e

# Hook: type: cron, schedule: "0 2 * * *"

# Fetch from primary source (Backstage)
curl -fsS "$BACKSTAGE_API/entities" | \
  jq '...' | lunar catalog --json '.components' -

# Augment with ownership data from a spreadsheet export
curl -fsS "$OWNERSHIP_SHEET_CSV" | \
  csvjson | jq '...' | lunar catalog --json '.components' -

# Add domain hierarchy from internal API
curl -fsS "$INTERNAL_API/domains" | \
  jq '...' | lunar catalog --json '.domains' -
```

## Plugin Structure

```
my-cataloger/
├── lunar-cataloger.yml    # Required: Plugin configuration
├── main.sh                # Main cataloger script
├── Dockerfile             # Optional: For additional dependencies
└── helper.sh              # Optional: Helper scripts
```

### lunar-cataloger.yml Reference

```yaml
version: 0

name: my-cataloger                    # Required: Must match directory name
description: What this cataloger does # Required: Brief description
author: team@example.com              # Required

# Recommended: specify container image
default_image: earthly/lunar-scripts:1.0.0

# === Landing page metadata (required for public plugins) ===
landing_page:
  display_name: "My Cataloger"        # Required: Max 50 chars, must end with "Cataloger"
  long_description: |                 # Required: Max 300 chars, used for hero tagline + meta description
    Sync components from XYZ into your Lunar catalog. Automatically 
    track ownership, domains, and metadata across your organization.
  category: "repository-and-ownership" # Required: See categories below
  status: "stable"                    # Required: stable|beta|experimental|deprecated
  icon: "assets/my-icon.svg"          # Required: Path relative to plugin directory
  
  # Related plugins for cross-linking (optional)
  related:
    - slug: "my-collector"
      type: "collector"
      reason: "Collects detailed data for discovered components"

# === Catalogers (sub-components) ===
catalogers:
  - name: sync-components             # Required: Unique within plugin
    description: |                    # Required: Multi-line description
      Syncs all components from XYZ including:
      - Feature A
      - Feature B
    mainBash: main.sh                 # Or: runBash: "inline script"
    hook:
      type: cron                      # Or: repo, component-repo
      schedule: "0 2 * * *"
    keywords: ["keyword1", "keyword2", "seo term"]  # Required: SEO keywords

# === Inputs (optional) ===
inputs:
  api_url:
    description: Base URL for API
    default: "https://api.example.com"
  org_name:
    description: Organization to sync
    # No default = required input

# === Secrets (optional) ===
secrets:
  - name: API_TOKEN
    description: API authentication token
    required: true

# === Example output (required for public plugins) ===
example_catalog_json: |
  {
    "components": {
      "github.com/acme/api": {
        "owner": "jane@example.com",
        "domain": "platform.backend",
        "tags": ["go", "production"]
      }
    },
    "domains": {
      "platform": {
        "description": "Platform services",
        "owner": "platform-team@example.com"
      }
    }
  }
```

### Landing Page Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `landing_page.display_name` | Yes | Human-readable name, max 50 chars, must end with "Cataloger" |
| `landing_page.long_description` | Yes | Marketing description, max 300 chars, used for hero + meta |
| `landing_page.category` | Yes | One of the 6 valid categories (see below) |
| `landing_page.status` | Yes | `stable`, `beta`, `experimental`, or `deprecated` |
| `landing_page.icon` | Yes | Path to SVG icon relative to plugin directory (file must exist) |
| `landing_page.related[]` | No | Array of related plugins (`slug`, `type`, `reason` max 80 chars) |
| `catalogers[].keywords` | Yes | Array of SEO keywords for this sub-cataloger (at least 1) |
| `inputs` | No | Configuration inputs (for website display, moved from README) |
| `secrets[]` | No | Array of secrets this cataloger needs (for website display) |
| `example_catalog_json` | No | Example Catalog JSON output (for website display, recommended) |

**Cross-validation:** The README title (`# ...`) must match `landing_page.display_name` exactly.

**Note:** `landing_page.requires` is not allowed for catalogers (only for policies).

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

Lunar runs catalogers inside Docker containers, providing isolation and reproducibility.

**Recommendation:** Use the official `earthly/lunar-scripts:1.0.0` image (or a custom image that inherits from it) for catalogers.

### Image Resolution Order

The image used to run a cataloger is determined in this order (first match wins):

1. **Cataloger-level `image`** — Set directly on the cataloger in `lunar-config.yml`
2. **Plugin-level `default_image`** — Set in `lunar-cataloger.yml`
3. **Global `default_image_catalogers`** — In `lunar-config.yml`
4. **Global `default_image`** — Fallback in `lunar-config.yml`
5. **Implicit default** — `native` (no container)

### Global Default Images

Configure default images in `lunar-config.yml`:

```yaml
version: 0

default_image: earthly/lunar-scripts:1.0.0
default_image_catalogers: earthly/lunar-scripts:1.0.0  # Optional override

# ... rest of configuration
```

### The `native` Value

The special value `native` explicitly opts out of containerized execution. The script runs directly on the host system.

Use `native` only when necessary (e.g., accessing host-specific tools or resources).

### Creating a Custom Image

When your cataloger requires additional dependencies, create a `Dockerfile` that inherits from the official base image:

```dockerfile
FROM earthly/lunar-scripts:1.0.0

# Install additional dependencies
RUN apk add --no-cache postgresql-client

# Or install specific tools
ARG TARGETARCH=amd64
RUN curl -sSL "https://example.com/tool-${TARGETARCH}.tar.gz" | tar xz && \
    mv tool /usr/local/bin/
```

### Accessing Inputs

Inputs are passed as environment variables with the prefix `LUNAR_VAR_` and the input name in uppercase:

```bash
#!/bin/bash
# If input is named "api_url", access it as:
echo "API URL: $LUNAR_VAR_API_URL"
```

## Best Practices

### 1. Always Use `set -e`

Exit on first error to avoid partial/incorrect data.

```bash
#!/bin/bash
set -e
```

### 2. Fail on API Errors

Exit with an error on failures to prevent corrupting the catalog with incomplete data. Better slightly outdated than corrupted.

```bash
RESPONSE=$(curl -fsS "$API_URL")
if [ $? -ne 0 ]; then
  echo "API unavailable, aborting sync"
  exit 1
fi
```

### 3. Use Structured Transformations

Use `jq` for complex JSON transformations.

```bash
# Good - clear transformation pipeline
curl -s "$API" | jq '
  [.items[] | select(.active) | {
    (.repo): {
      owner: .owner.email,
      domain: .team.name,
      tags: [.labels[].name]
    }
  }] | add
' | lunar catalog --json '.components' -
```

### 4. Include Logging

Log progress for debugging.

```bash
echo "Fetching components from Backstage..."
COMPONENTS=$(curl -fsS "$BACKSTAGE_API/entities")
echo "Found $(echo "$COMPONENTS" | jq 'length') components"
```

### 5. Keep Catalogers Focused

One cataloger should sync from one source. Create separate catalogers for different systems.

### 6. Test Locally

Use `lunar cataloger dev` to test catalogers locally:

```bash
# Run catalogers and output the resulting Catalog JSON
lunar cataloger dev --output-json
```

### 7. Document Your Sources

Document what external systems your cataloger syncs from and any required secrets.

### 8. View Current Catalog

Inspect the current catalog state:

```bash
lunar cataloger get-json
```
