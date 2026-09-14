# GitLab Cataloger

Discovers the GitLab groups a service account maintains and catalogs their projects as Lunar components.

## Overview

This cataloger syncs GitLab projects into the Lunar catalog without being told which groups to look in: it lists every top-level group the token's account is a maintainer of, then enumerates each group's projects including subgroups. It maps project topics to Lunar tags and supports filtering by visibility, project path, and topic. Onboarding a new group is an invite on the GitLab side, with no configuration change here — which is the point on an instance with many root-level groups. It works against gitlab.com as well as self-managed and Dedicated hosts via the `gitlab_host` input.

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | Default owner (if `default_owner` is configured) |
| `.components[*].domain` | string | Domain, from the group path with `domain_from_group_path` or from `default_domain` |
| `.components[*].tags[]` | array | Project topics, normalized and prefixed (e.g. `gl-backend`), plus `gitlab-visibility-<visibility>` and `gitlab-archived` on archived projects |
| `.components[*].meta.description` | string | Project description |
| `.components[*].meta.visibility` | string | Project visibility (`public`, `internal`, `private`) |
| `.components[*].meta.archived` | string | Whether the project is archived (`"true"`/`"false"`) |
| `.components[*].meta.default_branch` | string | Project default branch, omitted for a project with no commits |
| `.components[*].meta.project_id` | string | GitLab numeric project ID, stable across renames |
| `.components[*].meta.group` | string | Top-level group the project was discovered under |
| `.components[*].meta.topics` | string | Raw GitLab topics, comma-separated, before tag normalization |
| `.domains[*]` | object | Registers every domain the run emits, so the catalog passes the hub's domain-reference validation |

Component IDs are `<host>/<project path>`, using GitLab's canonical `path_with_namespace` — so a project in a subgroup is keyed as `gitlab.com/acme/payments/payment-api`, subgroups included. Taking the path from the API rather than from configuration is what keeps the casing canonical: Lunar's component identity is case-sensitive, so a hand-written group spelling that differs from GitLab's slug creates a second, dead identity for the same group.

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
        "project_id": "4218771",
        "group": "acme",
        "topics": "backend,go"
      }
    },
    "gitlab.com/globex/web/frontend-app": {
      "tags": ["gl-react", "gitlab-visibility-internal"],
      "meta": {
        "description": "Customer-facing web application",
        "visibility": "internal",
        "archived": "false",
        "default_branch": "main",
        "project_id": "4218903",
        "group": "globex",
        "topics": "React"
      }
    }
  }
}
```

</details>

### Topics become tags, normalized

GitLab topics are free text — any ASCII bar linebreaks — unlike GitHub's, which are already slug-shaped. Passed through verbatim, three things break selection downstream:

- A tag containing a space cannot be referenced from an `on:` expression at all. The expression is tokenized on whitespace, so `on: "gl-infra-mgmt Managed"` is a parse error — and it takes the whole expression with it, not just that one term.
- Parens do the same thing: they are token delimiters in the expression grammar, so a topic like `Managed (Internal)` would yield a tag no `on:` can reference. Other punctuation (`&`, `,`, `.`) lexes fine and is left alone.
- Tag matching is case-sensitive, so the tag `gl-Canonical` is silently not matched by the natural `on: [gl-canonical]`.

So topics are normalized before they become tags: lowercased, with runs of whitespace and parens collapsed to a single `-` and any leading or trailing `-` trimmed. `Infra Managed` becomes `gl-infra-managed`; `Managed (Internal)` becomes `gl-managed-internal`. The raw topics are preserved verbatim in `meta.topics` so nothing is lost. `allowed_topics` and `disallowed_topics` normalize both sides before comparing, so you can write either spelling in your config.

### Project lifecycle

Each run reports the projects that exist **now**; the catalog is not additive. The Hub replaces this cataloger's previous contribution with the latest one and retires components that no longer appear, so the catalog tracks the estate rather than accumulating everything ever seen.

| On GitLab | In the catalog |
|---|---|
| Project created | Becomes a component on the next run |
| Project deleted | Its component is retired on the next run |
| Project archived | Excluded by default, so its component is retired on the next run. With `include_archived: "true"` it stays, tagged `gitlab-archived` and with `meta.archived: "true"` |
| Project unarchived | Returns on the next run |
| Project renamed or moved between groups | Its path changes, so this is a retire plus a create: the old component is retired and a new one appears at the new path |
| Group created, service account invited | Discovered on the next run, with all its projects |
| Service account removed from a group | The group's projects are retired on the next run |

A rename does not carry component history across, because Lunar's component identity is the project path. `meta.project_id` carries GitLab's numeric project ID, which is stable across renames, so the two components can be correlated after the fact.

Because retirement follows from absence, a run that fails partway must not report a partial set. The cataloger exits non-zero on an API error rather than writing what it managed to read — a failed run leaves the previous catalog in place, which is better than mass-retiring components because of one bad response. The same reasoning applies per group: a group that fails to enumerate aborts the run rather than silently dropping its projects.

### Default branch

`meta.default_branch` is informational. The cataloger deliberately does not set the Catalog JSON `branch` field: a cataloger-declared branch is taken verbatim, so a branch read on a nightly schedule would go stale between runs, and a component pinned to a branch that no longer exists collects nothing. Leaving it unset lets the Hub resolve each component's default branch live.

## Catalogers

This plugin provides the following catalogers:

| Cataloger | Description |
|-----------|-------------|
| `groups` | Discovers every top-level group the token's account maintains and catalogs their projects, including subgroups |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 3 * * *` | Runs daily at 3am UTC |

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab@v1.0.0
```

Then set the token at **cataloger** scope — the default scope is `collector`, and a secret in the wrong scope is invisible to this plugin:

```bash
lunar secret set GL_TOKEN --scope cataloger
```

That is the whole configuration for the common case. There is no list of groups to maintain: the token's own group memberships are the scope, so you bring a group into the catalog by inviting the service account to it.

### Self-managed and Dedicated

Point `gitlab_host` at your instance:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab@v1.0.0
    with:
      gitlab_host: "gitlab.acme.com"
```

This matches the instance service account model, where one account is a maintainer of every top-level group Lunar serves. On gitlab.com, where group service accounts are per-group, a token still discovers exactly the groups its account belongs to — several tokens means several instances of this cataloger, distinguished with `name:` on the `uses:` line.

### Narrowing the catalog

Discovery is automatic, so scoping is done with path globs rather than a group list. Both match the project's full path within the host, so the leading segment is the group:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab@v1.0.0
    with:
      include_projects: "acme/*,globex/platform/*"   # only these
      exclude_projects: "*/sandbox/*,*/deprecated-*" # never these
```

### Advanced configuration

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab@v1.0.0
    with:
      gitlab_host: "gitlab.acme.com"
      include_public: "true"
      include_internal: "true"
      include_private: "true"
      include_archived: "false"
      exclude_projects: "*/sandbox/*"
      tag_prefix: "gl-"
      default_owner: "platform-team@acme.com"
      default_domain: "platform"
```

When `default_domain` is set, every discovered component gets that domain on its `.domain` field, and the domain is registered under `.domains` so the catalog passes the Hub's domain-reference validation. A domain definition in `lunar-config.yml` (or a later cataloger) takes precedence on merge, so you can set a richer description and owner there without this cataloger clobbering it.

### Domains from the group hierarchy

GitLab groups already encode a hierarchy, and Lunar domains are dotted paths, so the two map onto each other directly. Set `domain_from_group_path: "true"` and each component lands in a domain named after the group path that contains it:

```
acme/payments/payment-api   ->  domain  acme.payments
acme/web/frontend-app       ->  domain  acme.web
globex/checkout             ->  domain  globex
```

`default_domain` then becomes the root the hierarchy hangs under rather than a flat value — with `default_domain: "eng"` those become `eng.acme.payments`, `eng.acme.web`, `eng.globex`. That is how you keep a whole GitLab estate beneath one top-level domain.

Two details worth knowing. Every domain the run derives is registered under `.domains` in the same run, before the components that reference it — the Hub drops a component whose domain it cannot resolve, so for derived domains this is load-bearing rather than a formality. And a `.` inside a group path segment is folded to `-` (`acme/v1.2/svc` → `acme.v1-2`), because the dot is the domain separator and would otherwise invent a hierarchy level that does not exist in GitLab.

Leave it off (the default) and nothing changes: domains come only from `default_domain`, and with that empty the cataloger writes no domain at all, so components fall into the Hub's reserved `other`.

### Filter by topic (allowlist / blocklist)

You can opt projects into the catalog by **GitLab topic**. Tag the projects you want cataloged and set `allowed_topics`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/gitlab@v1.0.0
    with:
      allowed_topics: "lunar"          # only projects carrying the `lunar` topic
      disallowed_topics: "no-catalog"  # …but never projects carrying `no-catalog`
```

- **`allowed_topics`** — when set, a project is cataloged only if it carries **at least one** of the listed topics. Empty (default) means no allowlist: every project passes.
- **`disallowed_topics`** — a project carrying **any** of the listed topics is excluded. Block wins over allow.

Both lists compose with the visibility and path-pattern filters — a project must pass all of them.

## Source System

This cataloger reads the GitLab REST API (`/api/v4`) with `curl`, authenticating with the `GL_TOKEN` secret sent as a `PRIVATE-TOKEN` header. The token needs the `api` scope and belongs to a service account that is a maintainer of each top-level group Lunar should serve — the same account and token the Hub itself uses for GitLab. Its group memberships are the cataloger's scope, so no group list is configured anywhere. The same token works for gitlab.com, self-managed and Dedicated instances; only `gitlab_host` changes.

### Discovery and scale

Two steps per run. First, `/groups?top_level_only=true&min_access_level=40` lists the top-level groups where the account holds at least the maintainer role — only groups it is a member of, not every group on the instance. That level is fixed rather than configurable on purpose: maintainer is what the Hub itself requires of the GitLab service account, and group membership at that level is how the Hub decides what to serve, so the cataloger discovers exactly the groups the Hub can work with. Cataloging a group below it would create components whose webhooks can never be registered, which show up and then sit at zero checks forever. Then each group's projects are listed from `/groups/:id/projects?include_subgroups=true`, which covers the whole subtree in one pass, so subgroups are never enumerated separately.

Project listing uses **keyset pagination** (`order_by=id&sort=asc` plus `id_after`), walking until a page comes back empty. There is no configured ceiling on the number of projects or groups: a cap that silences itself is worse than a long run, so the cataloger pages until GitLab says there are no more.

Two pagination details are worth knowing, because both look like they work and don't:

- The `pagination=keyset` query parameter is **not** honoured on `/groups/:id/projects`. GitLab accepts it and still returns offset-paginated `Link` headers, including a `rel="last"`. Passing `id_after` explicitly is what makes the paging genuinely keyset, and is why the cataloger does not follow `Link: rel="next"`.
- On `/groups`, `id_after` is ignored entirely — that endpoint is offset-only. Group discovery therefore pages by `page=N` to the last page. It is bounded by the number of groups rather than projects, so offset paging is cheap there.

Projects **shared into** a group but owned elsewhere are excluded (`with_shared=false`). GitLab includes them by default, which would otherwise catalog projects outside the account's groups and duplicate any project shared into more than one of them.

### Rate limits

GitLab returns `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset` on every API response. The cataloger reads them to pace itself as the remaining budget runs low, and retries `429` and `5xx` responses with exponential backoff, honouring `Retry-After` when GitLab sends it. Requests that fail for a non-transient reason (`401`, `403`, `404`) abort the run rather than shrinking the reported project set.
