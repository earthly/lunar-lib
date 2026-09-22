# moon Cataloger

Reads the dependency graph a monorepo already declares in its [moon](https://moonrepo.dev) configuration and writes it into Lunar as component `paths`.

## Overview

A component named after a subdirectory already matches changes under it, but Lunar does not know that `apps/web` *consumes* `packages/auth` — so a commit touching only the shared library leaves `apps/web` un-evaluated. Closing that gap means listing every dependency in the service's `paths`, which is fine for one edge and unmaintainable for a thousand. A monorepo on moon has already declared those edges in `moon.yml`, because its build depends on them being right. This cataloger reads that graph and generates the `paths` list from it.

`paths` gates policy **evaluation**, not data attribution: widening it re-runs a service's policies on a library change, but does not move a CI run's collected data onto that service.

## Synced Data

| Path | Type | Description |
|------|------|-------------|
| `.components["<id>"].paths[]` | array | One `<dir>/*` glob per project the component transitively depends on. Repo-relative, sorted, de-duplicated. The component's *own* directory is not written — the hub already derives an implicit `<subdir>/*` from the component name |

Only `paths` is written — ownership, domains and tags come from whichever cataloger defines the component.

The hub appends arrays when merging, so these globs **union** with any `paths` declared in `lunar-config.yml` rather than replacing them. A path declared in both places appears twice — harmless for matching, but worth deleting from the config once this cataloger owns the list. (This is also why the component's own directory is omitted: the config sync materialises the implicit `<subdir>/*` onto every component, so emitting it here would duplicate it every time.)

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `dependency-paths` | Finds the moon project whose `source` is the component's subdirectory, takes its transitive `dependsOn` closure, and writes one `<dir>/*` glob per dependency reached |

A trailing `*` is a prefix match in Lunar and it crosses `/`, so one glob per project covers every file beneath it. Where the moon workspace root sits below the repository root, each `source` is prefixed with that offset to keep the globs repo-relative.

**Skips silently** (exit 0, nothing written):

- the component is the repository root — it already matches every path, so writing `paths` would *narrow* it
- the repository has no `.moon/` at or above the component directory
- the component's subdirectory is not a moon project
- the project has no dependencies once `exclude_scopes` is applied — there is nothing to add that the implicit `<subdir>/*` does not already cover

**Fails the run** (nothing written):

- `moon query projects` errors or returns unparseable output
- moon reports several projects and no dependency edges at all. An unresolvable toolchain looks exactly like that — moon exits 0 with an empty stderr and an edgeless graph — and publishing it would claim nothing in the repo depends on anything. Set `require_dependency_edges: "false"` for a workspace that genuinely declares none.

## Hook Type

| Cataloger | Hook | Schedule / Trigger | Description |
|-----------|------|--------------------|-------------|
| `dependency-paths` | `component-repo` (`clone-code: true`) | Every push to a component's repository | Runs once per component of the pushed repo, with the repo checked out at the pushed commit |

`clone-code: true` is what makes this work: moon reads `moon.yml` from a working tree, so the graph needs a real checkout rather than a GitHub API fetch. It needs no token and no network — moon is a single static binary and the declared edges come from files in the checkout — so it runs on air-gapped installs.

Being a per-component hook it **augments components that already exist** and cannot create them. Pair it with a component-defining cataloger such as [`github-org`](../github-org) or [`backstage-catalog-info-monorepo`](../backstage-catalog-info-monorepo), or declare the subcomponents in `lunar-config.yml`.

## Installation

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/moon@v1.16.0
```

No secrets or inputs are required. To keep test-only dependencies out of a service's paths:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/moon@v1.16.0
    with:
      exclude_scopes: "development"
```

Components whose paths should be managed must exist and be named after their subdirectory, e.g. `github.com/acme/monorepo/apps/web` for the moon project at `apps/web`.

## Source System

[moon](https://moonrepo.dev) — the `moon` binary is baked into this cataloger's image and runs against the checkout the hook provides. Requirements:

- **The repository uses moon**: a `.moon/workspace.yml` and a `moon.yml` per project. Repos without one are skipped.
- **Project sources match component subdirectories.** A moon project at `apps/web` maps to the component whose name ends `/apps/web`. A project that is not itself a Lunar component is still traversed as a dependency; it just gets no `paths` of its own.
- **Declared edges, not inferred ones.** moon can also infer dependencies from a language's own manifests, but that needs the language toolchain in the cataloger image, which this plugin does not ship. Workspaces relying on inference see fewer edges, and the edgeless-graph guard above is what stops that failing silently.

### Scope

Only moon is read today. The same three fields — project id, project directory, dependency ids — are what `go list`, `cargo metadata`, nx and turborepo all produce, so other graph sources belong behind this interface rather than in separate catalogers.

Auto-injecting moon into a repository that does not use it was prototyped and rejected: moon refuses to build a graph whose directory-level dependencies contain a cycle, which Go permits at package level, and silently reports zero edges when it cannot resolve a toolchain.
