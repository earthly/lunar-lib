# GitHub Org Cataloger

Catalogs all repositories from a GitHub organization as Lunar components.

## Overview

This cataloger syncs repositories from a GitHub organization into the Lunar catalog. It maps GitHub topics to Lunar tags (with a configurable prefix), supports filtering by visibility, repository name patterns, and repository topics (allow/blocklist), and can optionally stamp a default owner and domain on all components. It works against github.com as well as GitHub Enterprise Server (via the `github_host` input).

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
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
```

### Advanced Configuration

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
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
      max_repos_per_visibility: "10000"
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
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      github_host: "github.acme.com"
```

A full URL (e.g. `https://github.acme.com`) is also accepted — the scheme and
any trailing path are stripped automatically. Authentication for a GHE host uses
`LUNAR_SECRET_GH_ENTERPRISE_TOKEN` (routed to the GitHub CLI as
`GH_ENTERPRISE_TOKEN`), falling back to `LUNAR_SECRET_GH_TOKEN` if that secret is
not set — so a github.com and a GHE server can use distinct credentials. Component
IDs reflect the host, so a repo on GHE is keyed as `github.acme.com/<org>/<repo>`.

### Include Only Specific Repos

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      include_repos: "api-*,backend-*,frontend-*"
```

### Filter by Topic (allowlist / blocklist)

Instead of maintaining a repository-name list, you can opt repos into the
catalog by **GitHub topic**. Tag the repos you want cataloged (e.g. add the
`lunar` topic on GitHub) and set `allowed_topics`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme-corp"
      allowed_topics: "lunar"          # only repos carrying the `lunar` topic
      disallowed_topics: "no-catalog"  # …but never repos carrying `no-catalog`
```

- **`allowed_topics`** — when set, a repo is cataloged only if it carries **at
  least one** of the listed topics. Empty (default) means no allowlist: every
  repo passes.
- **`disallowed_topics`** — a repo carrying **any** of the listed topics is
  excluded. Block wins over allow, so a repo matching both an allowed and a
  disallowed topic is excluded.

Topics are matched exactly (case-sensitive) against the repository's GitHub
topics, and both lists compose with the visibility and name-pattern
(`include_repos` / `exclude_repos`) filters — a repo must pass all of them.

## Source System

This cataloger uses the GitHub CLI (`gh`) to query the GitHub API. It requires:

1. **GitHub CLI** installed and available in the container (included in custom image)
2. **Authentication** via `LUNAR_SECRET_GH_TOKEN` (same as other GitHub collectors) with appropriate scopes:
   - `repo` scope for private/internal repositories
   - `read:org` scope for public repositories only

   For GitHub Enterprise Server (`github_host` other than github.com) the
   cataloger reads `LUNAR_SECRET_GH_ENTERPRISE_TOKEN` and routes it to the GitHub
   CLI as `GH_ENTERPRISE_TOKEN`. If that secret is unset it falls back to
   `LUNAR_SECRET_GH_TOKEN`, so existing single-token setups keep working.

The cataloger makes API calls to list repositories and their topics.

### Scale and rate limits

This cataloger is built for large organizations (thousands of repositories):

- **Listing paginates through the GitHub GraphQL API** (100 repositories per
  page, cursor-based). This is *not* the GitHub Search API, so the well-known
  1,000-result search cap does **not** apply — the cataloger lists every repo in
  the org, well past 1,000.
- **Fetch ceiling.** Listing stops at `max_repos_per_visibility` repositories per
  visibility level (default `10000`). The default comfortably covers orgs with
  thousands of repos; raise it for a larger org. If a fetch returns exactly the
  ceiling, the cataloger logs a truncation warning so a partial catalog never
  goes unnoticed.
- **API cost is low.** Listing costs roughly one GraphQL rate-limit point per 100
  repositories (about 100 points to list 10,000 repos), against GitHub's default
  budget of 5,000 points/hour — a full run uses a small fraction of the quota.
  Listing calls retry with exponential backoff on primary/secondary rate-limit
  and transient errors.
- **Catalog output is written in small, byte-bounded batches.** Each discovered
  repo is emitted via `lunar catalog raw`, which the operator captures from the
  cataloger's stdout one line at a time. Components are packed into batches kept
  well under the container log-line size limit (~16 KB) so every batch is
  captured intact — an oversized line would be truncated by the log stream and
  silently drop repos. Repos are emitted in a stable, sorted order, so the
  catalog is deterministic run to run.

> **Note:** this covers *listing and cataloging* repositories. If you also run
> the companion `github` **collector** to gather per-repo settings, that makes
> API calls per repository — for a very large org, plan its schedule and
> concurrency accordingly, since per-repo work is where GitHub REST rate limits
> are more likely to matter.
