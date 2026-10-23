# Releasing lunar-lib

## Usage

From the repo root, on `main`, with a clean working tree:

```bash
./scripts/release.sh v0.42.0
```

## What it does

1. Creates branch and tag `vX.Y.Z` from current `HEAD`
2. Rewrites all `lunar-*.yml` files: `earthly/lunar-lib:*-main` → `earthly/lunar-lib:*-vX.Y.Z`
3. Rewrites all starter-pack refs: `@<anything>` → `@vX.Y.Z`
4. Commits, pushes branch + tag to `origin`, restores your previous branch

After that, CI builds and publishes images for the new tag. Consumers can then pin `@vX.Y.Z`.

## Before you run

- Make sure `HEAD` is what you want to release
- `HEAD`'s main CI must have finished, including `record pushed images for CVE scan`. The script checks with `gh` and refuses otherwise
- On the release branch, CI runs `lunar policy ok-release` on `HEAD` before it pushes any image. If a release-blocking policy fails, nothing publishes
- The script validates everything else (semver format, clean tree, no duplicate branch/tag, no leftover `-main` refs)

## AI agents

See [`.ai-implementation/releasing.md`](.ai-implementation/releasing.md) for the full release workflow — version proposals, CI monitoring, GitHub Release creation, notifications, and cronos updates.
