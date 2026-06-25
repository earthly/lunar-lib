# GitHub Org Cataloger

Catalogs all repositories from a GitHub organization as Lunar components.

## Overview

This cataloger syncs repositories from a GitHub organization into the Lunar catalog. It maps GitHub topics to Lunar tags (with a configurable prefix), supports filtering by visibility and repository name patterns, and can optionally stamp a default owner and domain on all components. It works against github.com as well as GitHub Enterprise Server (via the `github_host` input).

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | Default owner (if `default_owner` is configured) |
| `.components[*].domain` | string | Default domain (if `default_domain` is configured) |
| `.components[*].tags[]` | array | GitHub topics with prefix (e.g., `gh-backend`) |
| `.components[*].meta.description` | string | Repository description |
| `.components[*].meta.visibility` | string | Repository visibility (public, private, internal) |
| `.components[*].meta.archived` | string | Whether the repository is archived ("true"/"false") |
| `.domains[*]` | object | Registers the `default_domain` (if configured) so the catalog passes the hub's domain-reference validation |

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
      default_domain: "platform"
```

When `default_domain` is set, every discovered component gets that domain on its
`.domain` field, and the domain is registered under `.domains` so the catalog
passes the hub's domain-reference validation. A domain definition in
`lunar-config.yml` (or a later cataloger) takes precedence on merge, so you can
set a richer description/owner there and this cataloger won't clobber it.

### GitHub Enterprise Server

To catalog from a self-hosted GitHub Enterprise Server instead of github.com,
set `github_host` to your GHE hostname:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      github_host: "github.acme.com"
```

A full URL (e.g. `https://github.acme.com`) is also accepted — the scheme and
any trailing path are stripped automatically. Authentication uses the same
`LUNAR_SECRET_GH_TOKEN` secret regardless of host (it's routed to the GitHub CLI
as `GH_ENTERPRISE_TOKEN` for GHE hosts). Component IDs reflect the host, so a
repo on GHE is keyed as `github.acme.com/<org>/<repo>`.

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

1. **GitHub CLI** installed and available in the container (included in custom image)
2. **Authentication** via `LUNAR_SECRET_GH_TOKEN` (same as other GitHub collectors) with appropriate scopes:
   - `repo` scope for private/internal repositories
   - `read:org` scope for public repositories only

   The same secret is used for GitHub Enterprise Server; the cataloger routes it
   to the GitHub CLI as `GH_ENTERPRISE_TOKEN` when `github_host` is not github.com.

The cataloger makes API calls to list repositories and their topics. For large organizations, it fetches up to 10,000 repositories per visibility level.
