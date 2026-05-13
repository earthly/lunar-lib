# Cataloger Patterns

Common implementation patterns for Lunar catalogers. See [cataloger-reference.md](cataloger-reference.md) for the full hook / env-var / `lunar catalog` reference.

## Pattern 1: External API Sync (cron hook)

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

## Pattern 2: Database Sync (cron hook)

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

## Pattern 3: Central Repository Files (repo hook)

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

## Pattern 4: Component-Level Augmentation (component-repo hook)

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

## Pattern 5: GitHub Organization Sync (cron hook)

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

## Pattern 6: Multi-Source Aggregation (cron hook)

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

## Pattern 7: Component-JSON Heuristics (component-cron hook)

Classify components from signals in their existing Component JSON (data already collected by collectors). Uses a `component-cron` hook to re-evaluate each component on a schedule.

```bash
#!/bin/bash
set -e

# Hook: type: component-cron, schedule: "0 3 * * *"
# LUNAR_COMPONENT_ID is set for each component

COMPONENT_JSON="$(lunar component get-json "$LUNAR_COMPONENT_ID")"

# Tag based on k8s deployment namespace
if echo "$COMPONENT_JSON" | jq -e '.k8s.deployments[]? | select(.namespace == "prod")' >/dev/null; then
  lunar catalog component --tag production
fi

# Tag based on dependency license
if echo "$COMPONENT_JSON" | jq -e '.sca.dependencies[]? | select(.license == "AGPL-3.0")' >/dev/null; then
  lunar catalog component --tag compliance-review
fi
```

This pattern lets you treat the Component JSON itself as a classification signal — collectors fill it in, the cataloger reads it back to drive ownership / tags / domain assignment.
