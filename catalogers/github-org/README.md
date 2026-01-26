# `github-org` Cataloger

Catalogs all repositories from a GitHub organization as Lunar components.

## Overview

This cataloger syncs repositories from a GitHub organization into the Lunar catalog. It maps GitHub topics to Lunar tags (with a configurable prefix), supports filtering by visibility and repository name patterns, and can optionally set a default owner for all components.

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | Default owner (if configured) |
| `.components[*].tags[]` | array | GitHub topics with prefix (e.g., `gh-backend`) |
| `.components[*].meta.description` | string | Repository description |
| `.components[*].meta.visibility` | string | Repository visibility (public, private, internal) |
| `.components[*].meta.archived` | string | Whether the repository is archived ("true"/"false") |

<details>
<summary>Example Catalog JSON output</summary>

```json
{
  "components": {
    "github.com/acme/api": {
      "owner": "platform-team@acme.com",
      "tags": ["gh-backend", "gh-go", "gh-production"],
      "meta": {
        "description": "Main API service",
        "visibility": "private",
        "archived": "false"
      }
    },
    "github.com/acme/frontend": {
      "owner": "platform-team@acme.com",
      "tags": ["gh-frontend", "gh-typescript"],
      "meta": {
        "description": "Web application",
        "visibility": "private",
        "archived": "false"
      }
    },
    "github.com/acme/docs": {
      "tags": ["gh-documentation"],
      "meta": {
        "description": "Public documentation site",
        "visibility": "public",
        "archived": "false"
      }
    }
  }
}
```

</details>

## Catalogers

This plugin provides the following catalogers:

| Cataloger | Description |
|-----------|-------------|
| `repos` | Syncs all repositories from the GitHub organization |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 2 * * *` | Runs daily at 2am UTC |

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `org_name` | **Yes** | - | GitHub organization name to sync |
| `include_public` | No | `true` | Include public repositories |
| `include_private` | No | `true` | Include private repositories |
| `include_internal` | No | `true` | Include internal repositories (GitHub Enterprise) |
| `include_archived` | No | `false` | Include archived repositories |
| `include_repos` | No | `""` | Comma-separated glob patterns for repos to include (empty = all) |
| `exclude_repos` | No | `""` | Comma-separated glob patterns for repos to exclude |
| `tag_prefix` | No | `gh-` | Prefix for GitHub topics when converting to Lunar tags |
| `default_owner` | No | `""` | Default owner email for all components (empty = don't set) |

The `include_repos` and `exclude_repos` inputs accept comma-separated glob patterns:

- `*` matches any sequence of characters
- `?` matches any single character
- `[abc]` matches any character in the set

Examples:
- `api-*,backend-*` - Include repos starting with `api-` or `backend-`
- `sandbox-*,deprecated-*,*-test` - Exclude sandbox, deprecated, and test repos
- `*-service` - Match all repos ending with `-service`

## Secrets

- `GH_TOKEN` - GitHub personal access token with `repo` scope (or `read:org` for public repos only)

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
```

### Advanced Configuration

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      include_public: "true"
      include_private: "true"
      include_internal: "false"
      include_archived: "false"
      exclude_repos: "sandbox-*,deprecated-*,*-archive"
      tag_prefix: "gh-"
      default_owner: "platform-team@acme.com"
```

### Include Only Specific Repos

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      include_repos: "api-*,backend-*,frontend-*"
```

## Source System

This cataloger uses the GitHub CLI (`gh`) to query the GitHub API. It requires:

1. **GitHub CLI** installed and available in the container (included in base image)
2. **Authentication** via `GH_TOKEN` secret with appropriate scopes:
   - `repo` scope for private/internal repositories
   - `read:org` scope for public repositories only

The cataloger makes API calls to list repositories and their topics. For large organizations, it fetches up to 10,000 repositories per visibility level.
