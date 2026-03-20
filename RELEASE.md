# Releasing lunar-lib

## Usage

From the repo root, on `main`, with a clean working tree:

```bash
./scripts/release.sh v0.42.0
```

## What it does

1. Creates branch and tag `vX.Y.Z` from current `HEAD`
2. Rewrites all `lunar-*.yml` files: `earthly/lunar-lib:*-main` → `earthly/lunar-lib:*-vX.Y.Z`
3. Commits, pushes branch + tag to `origin`, restores your previous branch

After that, CI builds and publishes images for the new tag. Consumers can then pin `@vX.Y.Z`.

## Before you run

- Make sure `HEAD` is what you want to release
- The script validates everything else (semver format, clean tree, no duplicate branch/tag, no leftover `-main` refs)

## AI agent rules

- Only run when the user explicitly asks for a release
- Confirm the version and that `HEAD` is correct before running
- Run from repo root with `required_permissions: ["all"]` (needs SSH/GPG for push)
- After success, remind the user to wait for CI before pinning the new version downstream
- If it fails mid-way, inspect with `git status`/`branch`/`tag` — don't re-run the same version until cleanup is done
