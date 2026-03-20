# lunar-lib release process

This document explains how `scripts/release.sh` works and how an AI agent (or human) should run it to cut a release.

## What the script does

`scripts/release.sh` automates a **versioned snapshot** of the repo: it creates a Git branch and tag named after the version, pins Earthly-built container images in plugin manifests from the rolling `*-main` tags to immutable `*-<version>` tags, pushes everything to `origin`, then returns your working copy to the branch you started on.

Concretely, for a version argument `vX.Y.Z`:

1. **Validates** the version string (must be `v` + semver: `v1.2.3`).
2. **Refuses to run** if a branch or tag with that name already exists locally or on `origin`.
3. **Refuses to run** if the working tree is not clean (`git status` must be empty).
4. **Records** the current branch name.
5. **Creates** a new branch named `vX.Y.Z` from the current `HEAD`.
6. **Rewrites** every `lunar-*.yml` file under the repo: replaces  
   `earthly/lunar-lib:<anything>-main` → `earthly/lunar-lib:<anything>-vX.Y.Z`  
   (macOS and Linux `sed` are handled.)
7. **Verifies** that no `earthly/lunar-lib:...-main` remains in any `lunar-*.yml`; exits with an error if any slip through.
8. **Commits** all changes with message: `Pin images for vX.Y.Z`.
9. **Creates** a lightweight tag: `git tag vX.Y.Z` on that commit.
10. **Pushes** the branch and the tag to `origin`.
11. **Checks out** the branch you were on before step 5.

After a successful run, **CI is expected to build and publish** images tagged with `vX.Y.Z`. Downstream manifests can pin plugins with `@vX.Y.Z` (or equivalent) instead of `@main`.

**Note:** Manifest lines that use `earthly/lunar-lib:...` **without** a `-main` suffix (for example a custom tag) are **not** rewritten by this script. Only the `-main` → `-<version>` pattern is updated.

## Preconditions (not checked by the script)

Confirm these yourself; the script assumes them and will not validate them up front:

- **Correct commit:** Check out the branch that should become the release (almost always `main`) and ensure `HEAD` is exactly what you want released. The script does not merge PRs; it releases whatever `HEAD` is.
- **Human/team alignment:** Version number agreed, changelog or comms handled if your process requires it.

**Already enforced by the script:** `v`+semver version argument; clean working tree (`git status --porcelain` empty); branch and tag name not already present locally or on `origin`; after rewrite, no remaining `earthly/lunar-lib:...-main` in `lunar-*.yml`.

## How to run it

From the **repository root** of `lunar-lib`:

```bash
./scripts/release.sh vX.Y.Z
```

Example:

```bash
./scripts/release.sh v0.42.0
```

## Instructions for AI agents

1. **Do not run** `./scripts/release.sh` unless the user has **explicitly** asked to perform a release (or to run this script).

2. **Confirm release intent** with the user when ambiguous: that `HEAD` on the chosen branch is what should ship and the exact version string. The script validates version format, clean tree, and unused branch/tag names on its own.

3. **Run from repo root** so `find . -name 'lunar-*.yml'` covers all manifests.

4. **Git / push environment:** Pushing may require the same credentials as normal contributor pushes (SSH agent, signing, etc.). In restricted automation sandboxes, the push step may fail even if the script runs locally—use an environment where `git push` to `origin` is known to work.

5. **After success:** Remind the user that CI should publish images for the new tag, and that consumers should pin `@vX.Y.Z` after images exist.

6. **If the script fails after creating local branch/tag but before push:** The repo may be left on the version branch or in a partial state—use `git status`, `git branch`, and `git tag` to inspect; recovery may require manual reset, deleting a local tag/branch, or coordinating with the team. **Do not** re-run with the same version until the failed attempt’s objects are resolved.

## Quick reference

| Item | Value |
|------|--------|
| Script | `./scripts/release.sh` |
| Version format | `vMAJOR.MINOR.PATCH` (e.g. `v1.0.0`) |
| Files modified | All `lunar-*.yml` (image refs `...-main` → `...-<version>`) |
| Git artifacts | Branch `vX.Y.Z`, tag `vX.Y.Z`, both pushed to `origin` |
| Local end state | Checkout restored to the branch you started on |
