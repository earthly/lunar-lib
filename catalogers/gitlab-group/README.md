# GitLab Group Cataloger

Catalogs every project under a GitLab group, including its subgroups, as Lunar components.

## Overview

This cataloger syncs GitLab projects into the Lunar catalog. It maps project topics to Lunar tags (with a configurable prefix) and supports filtering by visibility, project path pattern, and topic allow/blocklist. Given no group it discovers every top-level group the token can see, which is what an instance service account on self-managed or Dedicated GitLab wants. It works against gitlab.com as well as self-managed and Dedicated hosts via the `gitlab_host` input.

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | Default owner (if `default_owner` is configured) |
| `.components[*].domain` | string | Default domain (if `default_domain` is configured) |
| `.components[*].tags[]` | array | Project topics with prefix (e.g. `gl-backend`), plus `gitlab-visibility-<visibility>` and `gitlab-archived` on archived projects |
| `.components[*].meta.description` | string | Project description |
| `.components[*].meta.visibility` | string | Project visibility (`public`, `internal`, `private`) |
| `.components[*].meta.archived` | string | Whether the project is archived (`"true"`/`"false"`) |
| `.components[*].meta.default_branch` | string | Project default branch, omitted for a project with no commits |
| `.components[*].meta.project_id` | string | GitLab numeric project ID, stable across renames |
| `.domains[*]` | object | Registers the `default_domain` (if configured) so the catalog passes the hub's domain-reference validation |

Component IDs are `<host>/<project path>`, using GitLab's canonical `path_with_namespace` — so a project in a subgroup is keyed as `gitlab.com/acme/payments/payment-api`. Taking the path from the API rather than from configuration is what keeps the casing canonical: Lunar's component identity is case-sensitive, so a hand-written group spelling that differs from GitLab's slug creates a second, dead identity for the same group.

<details>
<summary>Example Catalog JSON output</summary>

```json
{
  "components": {
    "gitlab.com/acme/payments/payment-api": {
      "owner": "platform-team@acme.com",
      "tags": ["gl-backend", "gl-go", "gitlab-visibility-private"],
      "meta": {
        "description": "Payment processing API service",
        "visibility": "private",
        "archived": "false",
        "default_branch": "main",
        "project_id": "4218771"
      }
    },
    "gitlab.com/acme/web/frontend-app": {
      "tags": ["gl-react", "gl-typescript", "gitlab-visibility-internal"],
      "meta": {
        "description": "Customer-facing web application",
        "visibility": "internal",
        "archived": "false",
        "default_branch": "main",
        "project_id": "4218903"
      }
    }
  }
}
```

</details>

### Project lifecycle

Each run reports the projects that exist **now**; the catalog is not additive. The Hub replaces this cataloger's previous contribution with the latest one and retires components that no longer appear, so the catalog tracks the group rather than accumulating everything ever seen.

| On GitLab | In the catalog |
|---|---|
| Project created | Becomes a component on the next run |
| Project deleted | Its component is retired on the next run |
| Project archived | Excluded by default, so its component is retired on the next run. With `include_archived: "true"` it stays, tagged `gitlab-archived` and with `meta.archived: "true"` |
| Project unarchived | Returns on the next run |
| Project renamed or moved between groups | Its path changes, so this is a retire plus a create: the old component is retired and a new one appears at the new path |

A rename does not carry component history across, because Lunar's component identity is the project path. `meta.project_id` carries GitLab's numeric project ID, which is stable across renames, so the two components can be correlated after the fact.

Because retirement follows from absence, a run that fails partway must not report a partial set. The cataloger exits non-zero on an API error rather than writing what it managed to read — a failed run leaves the previous catalog in place, which is better than mass-retiring components because of one bad response.

### Default branch

`meta.default_branch` is informational. The cataloger deliberately does not set the Catalog JSON `branch` field: a cataloger-declared branch is taken verbatim, so a branch read on a nightly schedule would go stale between runs, and a component pinned to a branch that no longer exists collects nothing. Leaving it unset lets the Hub resolve each component's default branch live.

## Catalogers

This plugin provides the following catalogers:

| Cataloger | Description |
|-----------|-------------|
| `projects` | Syncs all projects under the configured GitLab groups, including subgroups |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 3 * * *` | Runs daily at 3am UTC |

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab-group@v1.0.0
    with:
      groups: "acme"
```

Then set the token at **cataloger** scope — the default scope is `collector`, and a secret in the wrong scope is invisible to this plugin:

```bash
lunar secret set GL_TOKEN --scope cataloger
```

### Self-managed and Dedicated

Point `gitlab_host` at your instance, and leave `groups` empty to catalog every top-level group the token's account can see:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab-group@v1.0.0
    with:
      gitlab_host: "gitlab.acme.com"
```

This matches the instance service account model: you bring a group into the catalog by inviting the service account to it, with no configuration change here. To catalog a fixed set of groups instead, list them — each covers its own subgroups:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab-group@v1.0.0
    with:
      gitlab_host: "gitlab.acme.com"
      groups: "acme,globex/platform"
```

### Advanced configuration

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab-group@v1.0.0
    with:
      groups: "acme"
      include_public: "true"
      include_internal: "true"
      include_private: "true"
      include_archived: "false"
      exclude_projects: "acme/sandbox/*,*/deprecated-*"
      tag_prefix: "gl-"
      default_owner: "platform-team@acme.com"
      default_domain: "platform"
```

When `default_domain` is set, every discovered component gets that domain on its `.domain` field, and the domain is registered under `.domains` so the catalog passes the Hub's domain-reference validation. A domain definition in `lunar-config.yml` (or a later cataloger) takes precedence on merge, so you can set a richer description and owner there without this cataloger clobbering it.

### Filter by topic (allowlist / blocklist)

Instead of maintaining a project path list, you can opt projects into the catalog by **GitLab topic**. Tag the projects you want cataloged and set `allowed_topics`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab-group@v1.0.0
    with:
      groups: "acme"
      allowed_topics: "lunar"          # only projects carrying the `lunar` topic
      disallowed_topics: "no-catalog"  # …but never projects carrying `no-catalog`
```

- **`allowed_topics`** — when set, a project is cataloged only if it carries **at least one** of the listed topics. Empty (default) means no allowlist: every project passes.
- **`disallowed_topics`** — a project carrying **any** of the listed topics is excluded. Block wins over allow.

Topics are matched exactly (case-sensitive), and both lists compose with the visibility and path-pattern filters — a project must pass all of them.

## Source System

This cataloger reads the GitLab REST API (`/api/v4`) with `curl`, authenticating with the `GL_TOKEN` secret sent as a `PRIVATE-TOKEN` header. The token needs the `api` scope and an account that is a member of the groups being cataloged; Lunar's GitLab service account, a maintainer of each top-level group it serves, already satisfies this. The same token works for gitlab.com, self-managed and Dedicated instances — only `gitlab_host` changes.

### Scale

Projects are listed from `/groups/:id/projects?include_subgroups=true` using **keyset pagination** (`order_by=id&sort=asc` plus `id_after`), walking until a page comes back empty. There is no configured ceiling on the number of projects: a cap that silences itself is worse than a long run, so the cataloger pages until GitLab says there are no more.

Note that the `pagination=keyset` query parameter is **not** honoured on this endpoint — GitLab accepts it and still returns offset-paginated `Link` headers. Passing `id_after` explicitly is what makes the paging genuinely keyset, and is why the cataloger does not follow `Link: rel="next"`.

Top-level group discovery (when `groups` is empty) uses `/groups?top_level_only=true`, which supports **offset** pagination only — `id_after` is silently ignored there. That listing is bounded by the number of top-level groups rather than projects, so offset paging is cheap; it is still walked to the last page, never truncated.

Projects **shared into** a group but owned elsewhere are excluded (`with_shared=false`). GitLab includes them by default, which would otherwise catalog projects outside the configured groups and duplicate any project shared into more than one of them.

### Rate limits

GitLab returns `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset` on every API response. The cataloger reads them to pace itself as the remaining budget runs low, and retries `429` and `5xx` responses with exponential backoff, honouring `Retry-After` when GitLab sends it. Requests that fail for a non-transient reason (`401`, `403`, `404`) abort the run rather than shrinking the reported project set.
