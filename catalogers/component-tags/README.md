# Component Tags Cataloger

Applies platform-controlled tags to components from a YAML file checked into your Lunar config repo.

## Overview

This cataloger reads a YAML file from your Lunar config repo — the same repo that holds `lunar-config.yml` — and applies the tags it lists to the named components. Because the file lives in the config repo, the tags are **platform-controlled**: they're governed by that repo's review and branch protection, not by metadata a developer can set on their own service. It's a generic "apply arbitrary tags to arbitrary components" mechanism — the canonical use is centrally managing policy exceptions (e.g. a `release-bypass` allowlist) where the tag must come from platform, not the team being exempted. Tags are merged into the catalog additively, so they layer on top of whatever other catalogers contribute.

## Synced Data

This cataloger writes to the following Catalog JSON path:

| Path | Type | Description |
|------|------|-------------|
| `.components["<id>"].tags[]` | array | The tags listed for `<id>` in the config-repo tags file. Merged additively into the component's existing tags — other catalogers' tags are preserved. |

It writes **only** tags. Owner, domain, and other catalog fields are left to component-defining catalogers (see [Layering](#layering-with-a-component-defining-cataloger)).

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `sync` | Reads the tags file from a checkout of the Lunar config repo, then writes each entry's tags to `.components["<id>"].tags` in the Catalog JSON |

## Hook Type

| Hook | Trigger | Description |
|------|---------|-------------|
| `repo` | Commits to `config_repo` | Runs on every push to the Lunar config repo, with the repo checked out (`clone-code: true`), reading the tags file from the working tree |

The `repo` hook fires whenever the configured config repo receives a commit, so a change to the tags file takes effect the moment it merges — no waiting for a scheduled cron. Because the repo is checked out, the cataloger reads the file straight from the working tree: no GitHub token and no API call are required.

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/component-tags@v1.0.0
    with:
      config_repo: "github://acme/lunar"   # your Lunar config repo (holds lunar-config.yml)
      # tags_file: "component-tags.yml"      # optional — this is the default (repo root)
```

Then check the tags file into that same repo. The schema is a `components` map of component ID → tags to apply:

```yaml
# component-tags.yml — platform-controlled component tags.
# Tags here are MERGED into each component's catalog tags (additive).
components:
  github.com/acme/payment-api:
    tags: [release-bypass, tier1]
  github.com/acme/legacy-billing:
    tags: [release-bypass]
  github.com/acme/web-app:
    tags: [frontend]
```

See [`component-tags.example.yml`](component-tags.example.yml) for a fuller example.

### Layering with a Component-Defining Cataloger

This cataloger applies tags to components by ID; it does not own ownership or domain. Run a component-defining cataloger such as [`github-org`](../github-org) so the IDs in the tags file line up with cataloged components:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/component-tags@v1.0.0
    with:
      config_repo: "github://acme/lunar"
```

### Using the Tags in Policies

The point of platform-controlled tags is to drive policy scoping. A policy or initiative can be scoped to run only where a tag is **not** present, implementing an allowlist that developers can't edit:

```yaml
policies:
  - uses: github.com/earthly/lunar-lib/policies/sca@v1.0.0
    on: [soc2]
    not_on: [release-bypass]   # skip the gate for components platform has exempted
```

A component lands on the exemption list only by platform adding it to `component-tags.yml` and merging that change through the config repo's review.

## Source System

The "source system" is your own Lunar **config repo** — there's no external service, API, or credential involved. On each commit to `config_repo`, the hub checks the repo out and this cataloger reads `tags_file` (default `component-tags.yml`, at the repo root) from the working tree.

The file is a single YAML document with one top-level key:

| Key | Type | Description |
|-----|------|-------------|
| `components` | map | Maps a component ID (e.g. `github.com/acme/api`) to an object with a `tags` array. Each component's tags are applied to `.components["<id>"].tags`. |

Notes:

- **Additive only (v1).** Tags are merged into the catalog, never removed. To stop applying a tag, delete it from the file; it stops being contributed on the next sync. (Removing a tag another cataloger also sets is out of scope.)
- **Reference known component IDs.** IDs should match components a component-defining cataloger discovers. List only IDs you intend to tag; pair with a cataloger like `github-org`.
- **Governance is the config repo's.** Whatever controls merges to your config repo (CODEOWNERS, branch protection, required reviews) controls who can change these tags.
